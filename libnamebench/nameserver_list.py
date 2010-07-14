# Copyright 2009 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Classes to work with bunches of nameservers."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import datetime
import operator
import os
import pickle
import Queue
import random
import subprocess
import sys
import tempfile
import threading
import time

# 3rd party libraries
import dns.resolver

import conn_quality
import nameserver
import sys_nameservers
import addr_util
import util

NS_CACHE_SLACK = 2
CACHE_VER = 4


PREFERRED_HEALTH_TIMEOUT_MULTIPLIER = 1.5
SYSTEM_HEALTH_TIMEOUT_MULTIPLIER = 2
TOO_DISTANT_MULTIPLIER = 4.75
MAX_NEARBY_SERVERS = 400

# If we can't ping more than this, go into slowmode.
MIN_PINGABLE_PERCENT = 20
MIN_HEALTHY_PERCENT = 10
SLOW_MODE_THREAD_COUNT = 6

# Windows behaves in unfortunate ways if too many threads are specified
if sys.platform == 'win32':
  MAX_SANE_THREAD_COUNT = 32
else:
  MAX_SANE_THREAD_COUNT = 100

# Slow down for these, as they are used for timing.
MAX_INITIAL_HEALTH_THREAD_COUNT = 35


class OutgoingUdpInterception(Exception):

  def __init__(self, value):
    self.value = value

  def __str__(self):
    return repr(self.value)


class TooFewNameservers(Exception):

  def __init__(self, value):
    self.value = value

  def __str__(self):
    return repr(self.value)


class ThreadFailure(Exception):

  def __init__(self):
    pass


class QueryThreads(threading.Thread):
  """Quickly see which nameservers are awake."""

  def __init__(self, input_queue, results_queue, action_type, checks=None):
    threading.Thread.__init__(self)
    self.input = input_queue
    self.action_type = action_type
    self.results = results_queue
    self.checks = checks
    self.halt = False

  def stop(self):
    self.halt = True

  def run(self):
    """Iterate over the queue, processing each item."""
    while not self.halt and not self.input.empty():
      # check_wildcards is special: it has a tuple of two nameservers
      if self.action_type == 'wildcard_check':
        try:
          (ns, other_ns) = self.input.get_nowait()
        except Queue.Empty:
          return
        if ns.is_disabled or other_ns.is_disabled:
          self.results.put(None)
          continue
        else:
          self.results.put((ns, ns.TestSharedCache(other_ns)))
      # everything else only has a single nameserver.
      else:
        try:
          ns = self.input.get_nowait()
        except Queue.Empty:
          return

        if ns.is_disabled:
          self.results.put(None)
          continue
        if self.action_type == 'ping':
          self.results.put(ns.CheckHealth(fast_check=True))
        elif self.action_type == 'health':
          self.results.put(ns.CheckHealth(sanity_checks=self.checks))
        elif self.action_type == 'final':
          self.results.put(ns.CheckHealth(sanity_checks=self.checks, final_check=True))
        elif self.action_type == 'port_behavior':
          self.results.put(ns.CheckHealth(sanity_checks=self.checks, port_check=True))
        elif self.action_type == 'censorship':
          self.results.put(ns.CheckCensorship(self.checks))
        elif self.action_type == 'store_wildcards':
          self.results.put(ns.StoreWildcardCache())
        else:
          raise ValueError('Invalid action type: %s' % self.action_type)


class NameServers(list):

  def __init__(self):
    self._ips = set()
    self.thread_count = MAX_SANE_THREAD_COUNT
    super(NameServers, self).__init__()

  @property
  def preferred(self):
    return [x for x in self if x.is_preferred]

  @property
  def enabled_preferred(self):
    return [x for x in self.preferred if not x.is_disabled]

  @property
  def secondaries(self):
    return [x for x in self.SortByNearest() if not x.is_preferred]

  @property
  def enabled_secondaries(self):
    return [x for x in self.secondaries if not x.is_disabled and not x.is_hidden ]

  @property
  def enabled_servers(self):
    return [x for x in self if not x.is_disabled and not x.is_hidden]

  @property
  def visible_servers(self):
    return [x for x in self if not x.is_hidden]

  @property
  def check_average(self):
    return util.CalculateListAverage([x.check_average for x in self if not x.is_disabled])

  def msg(self, msg, count=None, total=None, **kwargs):
    if self.status_callback:
      self.status_callback(msg, count=count, total=total, **kwargs)
    else:
      print '%s [%s/%s]' % (msg, count, total)

  def _GetObjectForIP(self, ip):
    return [x for x in self if x.ip == ip][0]

  def append(self, ns):
    """Add a nameserver to the list, guaranteeing uniqueness."""
    if ns.ip in self._ips:
      print "%s already exists, adding tags: %s" % (ns.ip, ns.tags)
      existing_ns = self._GetObjectForIP(ns.ip)
      existing_ns.tags.update(ns.tags)
    else:
#      print "Adding: %s [%s]" % (ns.name, ns.ip)
      super(NameServers, self).append(ns)
      self._ips.add(ns.ip)

  def SetTimeouts(self, timeout, ping_timeout, health_timeout):
    if len(self.enabled_servers) > 1:
      cq = conn_quality.ConnectionQuality(status_callback=self.status_callback)
      (intercepted, unused_level, multiplier) = cq.CheckConnectionQuality()[0:3]
      if intercepted:
        raise OutgoingUdpInterception(
            'Your router or Internet Service Provider appears to be intercepting '
            'and redirecting all outgoing DNS requests. This means you cannot '
            'benchmark or utilize alternate DNS servers. Please adjust your '
            'router configuration or file a support request with your ISP.'
        )

      if multiplier > 1:
        health_timeout *= multiplier
        ping_timeout *= multiplier
        self.msg('Applied %.2fX timeout multiplier due to congestion: %2.1f ping, %2.1f health.'
                 % (multiplier, ping_timeout, health_timeout))

    for ns in self:
      ns.timeout = timeout
      ns.ping_timeout = ping_timeout
      ns.health_timeout = health_timeout

  def FilterByTag(self, include_tags=None, require_tags=None):
    print "Filter: %s by %s" % (include_tags, require_tags)
    
    for ns in self:
      if include_tags:
        if not ns.MatchesTags(include_tags):
#          print "%s does not have %s" % (ns, include_tags)
          ns.is_hidden = True
      if require_tags:
        for tag in require_tags:
          if not ns.HasTag(tag):
#            print "%s does not have %s" % (ns, tag)
            ns.is_hidden = True
    if not self.enabled_servers:
      raise TooFewNameservers('No nameservers specified matched tags %s %s' % (include_tags, require_tags))
    self.msg("%s of %s nameservers are available after tag filtering." % (len(self.visible_servers), len(self)))

  def FilterByProximity(self, latitude, longitude, country, asn, hostname):
    print "PROXIMITY DOES NOTHING"

  def InvokeSecondaryCache(self):
    """Delete secondary ips that do not exist in the cache file."""
    cached = False
    if self.cache_dir:
      cpath = self._SecondaryCachePath()
      cache_data = self._LoadSecondaryCache(cpath)
      if cache_data:
        for ns in self:
          ns.warnings = set()
          ns.checks = []
        cached = True
        cached_ips = [x.ip for x in cache_data if not x.is_preferred]
        for ns in list(self.secondaries):
          if ns.ip not in cached_ips:
            self.remove(ns)
    return cached

  def RemoveBrokenServers(self, delete_unwanted=False):
    """Quietly remove broken servers."""
    for ns in list(self):
      if ns.is_disabled and delete_unwanted and (ns.is_ipv6 or not ns.is_preferred):
        self.remove(ns)

  def DisableDistantServers(self, multiplier=TOO_DISTANT_MULTIPLIER, max_servers=MAX_NEARBY_SERVERS):
    """Disable servers who's fastest duration is multiplier * average of best 10 servers."""

    self.RemoveBrokenServers(delete_unwanted=True)
    secondaries = self.secondaries
    fastest = [x for x in self.SortByFastest() if not x.is_disabled ][:10]
    best_10 = util.CalculateListAverage([x.fastest_check_duration for x in fastest])
    cutoff = best_10 * multiplier
    self.msg("Removing secondary nameservers slower than %0.2fms (max=%s)" % (cutoff, max_servers))
    for idx, ns in enumerate(secondaries):
      if (ns.fastest_check_duration > cutoff) or idx > max_servers:
        self.remove(ns)

  def DisableUnwantedServers(self, target_count, delete_unwanted=False):
    """Given a target count, delete nameservers that we do not plan to test."""
    self.RemoveBrokenServers(delete_unwanted)

    # Magic secondary mixing algorithm:
    # - Half of them should be the "nearest" nameservers
    # - Half of them should be the "fastest average" nameservers
    preferred_count = len(self.enabled_preferred)
    secondaries_needed = target_count - preferred_count
    if secondaries_needed < 1 or not self.secondaries:
      return
    nearest_needed = int(secondaries_needed / 2.0)

    if secondaries_needed < 50:
      self.msg("Picking %s secondary servers to use (%s nearest, %s fastest)" %
               (secondaries_needed, nearest_needed, secondaries_needed - nearest_needed))

    # Phase two is picking the nearest secondary server
    secondaries_to_keep = []
    for ns in self.SortByNearest():

      if not ns.is_preferred and not ns.is_disabled:
        if not secondaries_to_keep and secondaries_needed < 15:
          self.msg('%s appears to be the nearest regional (%0.2fms)' % (ns, ns.fastest_check_duration))
        secondaries_to_keep.append(ns)
        if len(secondaries_to_keep) >= nearest_needed:
          break

    # Phase three is removing all of the slower secondary servers
    for ns in self.SortByFastest():
      if not ns.is_preferred and not ns.is_disabled and ns not in secondaries_to_keep:
        secondaries_to_keep.append(ns)
        if len(secondaries_to_keep) >= secondaries_needed:
          break

    for ns in self.secondaries:
      if ns not in secondaries_to_keep:
#        print "REMOVE: Fastest: %0.2f Avg: %0.2f:  %s - %s" % (ns.fastest_check_duration, ns.check_average, ns, ns.checks)
        self.remove(ns)
#      else:
#        print "KEEP  : Fastest: %0.2f Avg: %0.2f:  %s - %s" % (ns.fastest_check_duration, ns.check_average, ns, ns.checks)

  def CheckHealth(self, sanity_checks=None, max_servers=11):
    """Filter out unhealthy or slow replica servers."""
    self.msg('Building initial DNS cache for %s nameservers (%s threads)' %
             (len(self.enabled_servers), self.thread_count))
    self.PingNameServers()
    if len(self.enabled_servers) > max_servers:
      self.DisableDistantServers(NS_CACHE_SLACK, max_servers)
    self.RunHealthCheckThreads(sanity_checks['primary'])
    if len(self.enabled_servers) > max_servers:
      self._DemoteSecondaryGlobalNameServers()
      self.DisableUnwantedServers(target_count=int(max_servers * NS_CACHE_SLACK),
                                  delete_unwanted=True)
    # TODO(tstromberg): Insert caching here.
    if len(self.enabled_servers) > 1:
      self.CheckCacheCollusion()
      self.DisableUnwantedServers(max_servers)

    self.RunFinalHealthCheckThreads(sanity_checks['secondary'])
    if not self.enabled_servers:
      raise TooFewNameservers('None of the nameservers tested are healthy')

  def CheckCensorship(self, sanity_checks):
    pass

  def _RemoveGlobalWarnings(self):
    """If all nameservers have the same warning, remove it. It's likely false."""
    ns_count = len(self.enabled_servers)
    seen_counts = {}

    # No sense in checking for duplicate warnings if we only have one server.
    if len(self.enabled_servers) == 1:
      return

    for ns in self.enabled_servers:
      for warning in ns.warnings:
        seen_counts[warning] = seen_counts.get(warning, 0) + 1

    for warning in seen_counts:
      if seen_counts[warning] == ns_count:
        self.msg('All nameservers have warning: %s (likely a false positive)' % warning)
        for ns in self.enabled_servers:
          ns.warnings.remove(warning)

  def _DemoteSecondaryGlobalNameServers(self):
    """For global nameservers, demote the slower IP to secondary status."""
    seen = {}
    for ns in self.SortByFastest():
      if ns.is_preferred:
        # TODO(tstromberg): Have a better way of denoting secondary anycast.
        provider = ns.name.replace('-2', '')
        if provider in seen and not ns.is_system:
          faster_ns = seen[provider]
          self.msg('Making %s the primary anycast - faster than %s by %2.2fms' %
                   (faster_ns.name_and_node, ns.name_and_node, ns.check_average - faster_ns.check_average))
          ns.is_preferred = False
        else:
          seen[provider] = ns

  def _SecondaryCachePath(self):
    """Find a usable and unique location to store health results."""
    secondary_ips = [x.ip for x in self.secondaries]
    checksum = hash(str(sorted(secondary_ips)))
    basefile = '.'.join(map(str, ('namebench', CACHE_VER, len(secondary_ips),
                                  '_'.join(self.system_nameservers),
                                  self.num_servers,
                                  self.requested_health_timeout, checksum)))
    return os.path.join(self.cache_dir, basefile)

  def InvalidateSecondaryCache(self):
    cpath = self._SecondaryCachePath()
    if os.path.exists(cpath):
      self.msg('Removing %s' % cpath)
      os.unlink(cpath)

  def _LoadSecondaryCache(self, cpath):
    """Check if our health cache has any good data."""
    if os.path.exists(cpath) and os.path.isfile(cpath):
#      self.msg('Loading local server health cache: %s' % cpath)
      cf = open(cpath, 'r')
      try:
        return pickle.load(cf)
      except EOFError:
        self.msg('No cached nameserver data found')
    return False

  def _UpdateSecondaryCache(self, cpath):
    """Update the cache with our object."""
    cf = open(cpath, 'w')
    try:
      pickle.dump(list(self), cf)
    except TypeError, exc:
      self.msg('Could not save cache: %s' % exc)

  def SortByFastest(self):
    """Return a list of healthy servers in fastest-first order."""
    return sorted(self.visible_servers, key=operator.attrgetter('check_average'))

  def SortByNearest(self):
    """Return a list of healthy servers in fastest-first order."""
    return sorted(self.visible_servers, key=operator.attrgetter('fastest_check_duration'))

  def ResetTestResults(self):
    """Reset the testng status of all disabled hosts."""
    return [ns.ResetTestStatus() for ns in self]

  def CheckCacheCollusion(self):
    """Mark if any nameservers share cache, especially if they are slower."""
    self.RunWildcardStoreThreads()
    sleepy_time = 4
    self.msg("Waiting %ss for TTL's to decrement." % sleepy_time)
    time.sleep(sleepy_time)

    test_combos = []
    good_nameservers = [x for x in self.SortByFastest() if not x.is_disabled]
    for ns in good_nameservers:
      for compare_ns in good_nameservers:
        if ns != compare_ns:
          test_combos.append((compare_ns, ns))

    results = self.RunCacheCollusionThreads(test_combos)
    while not results.empty():
      (ns, shared_ns) = results.get()
      if shared_ns:
        ns.shared_with.add(shared_ns)
        shared_ns.shared_with.add(ns)
        if ns.is_disabled or shared_ns.is_disabled:
          continue

        if ns.check_average > shared_ns.check_average:
          slower = ns
          faster = shared_ns
        else:
          slower = shared_ns
          faster = ns

        if slower.system_position == 0:
          faster.is_disabled = 'Shares-cache with current primary DNS server'
          slower.warnings.add('Replica of %s' % faster.ip)
        elif slower.is_preferred and not faster.is_preferred:
          faster.is_disabled = 'Replica of %s [%s]' % (slower.name, slower.ip)
          slower.warnings.add('Replica of %s [%s]' % (faster.name, faster.ip))
        else:
          diff = slower.check_average - faster.check_average
          self.msg("Disabling %s - slower replica of %s by %0.1fms." % (slower.name_and_node, faster.name_and_node, diff))
          slower.is_disabled = 'Slower replica of %s [%s]' % (faster.name, faster.ip)
          faster.warnings.add('Replica of %s [%s]' % (slower.name, slower.ip))

  def _LaunchQueryThreads(self, action_type, status_message, items,
                          thread_count=None, **kwargs):
    """Launch query threads for a given action type.

    Args:
      action_type: a string describing an action type to pass
      status_message: Status to show during updates.
      items: A list of items to pass to the queue
      thread_count: How many threads to use (int)
      kwargs: Arguments to pass to QueryThreads()

    Returns:
      results_queue: Results from the query tests.

    Raises:
      TooFewNameservers: If no tested nameservers are healthy.
    """
    threads = []
    input_queue = Queue.Queue()
    results_queue = Queue.Queue()

    # items are usually nameservers
    random.shuffle(items)
    for item in items:
      input_queue.put(item)

    if not thread_count:
      thread_count = self.thread_count
    if thread_count > len(items):
      thread_count = len(items)

    status_message += ' (%s threads)' % thread_count

    self.msg(status_message, count=0, total=len(items))
    for _ in range(0, thread_count):
      thread = QueryThreads(input_queue, results_queue, action_type, **kwargs)
      try:
        thread.start()
      except:
        self.msg("ThreadingError with %s threads: waiting for completion before retrying." % thread_count)
        for thread in threads:
          thread.stop()
          thread.join()
        raise ThreadFailure()
      threads.append(thread)

    while results_queue.qsize() != len(items):
      self.msg(status_message, count=results_queue.qsize(), total=len(items))
      time.sleep(0.5)

    self.msg(status_message, count=results_queue.qsize(), total=len(items))
    for thread in threads:
      thread.join()

    if not self.enabled_servers:
      raise TooFewNameservers('None of the %s nameservers tested are healthy' % len(self.visible_servers))

    return results_queue

  def RunCacheCollusionThreads(self, test_combos):
    """Schedule and manage threading for cache collusion checks."""
    return self._LaunchQueryThreads('wildcard_check', 'Running cache-sharing checks on %s servers' % len(self.enabled_servers), test_combos)

  def PingNameServers(self):
    """Quickly ping nameservers to see which are available."""
    start = datetime.datetime.now()
    try:
      results = self._LaunchQueryThreads('ping', 'Checking nameserver availability', list(self.enabled_servers))
    except ThreadFailure:
      self.msg("It looks like you couldn't handle %s threads, trying again with %s (slow)" % (self.thread_count, SLOW_MODE_THREAD_COUNT))
      self.thread_count = SLOW_MODE_THREAD_COUNT
      self.ResetTestResults()
      results = self._LaunchQueryThreads('ping', 'Checking nameserver availability', list(self.enabled_servers))

    success_rate = self.GetHealthyPercentage()
    if success_rate < MIN_PINGABLE_PERCENT:
      self.msg('How odd! Only %0.1f percent of name servers were pingable. Trying again with %s threads (slow)'
               % (success_rate, SLOW_MODE_THREAD_COUNT))
      self.ResetTestResults()
      self.thread_count = SLOW_MODE_THREAD_COUNT
      results = self._LaunchQueryThreads('ping', 'Checking nameserver availability', list(self.enabled_servers))
    if self.enabled_servers:
      self.msg('%s of %s servers are available (duration: %s)' %
               (len(self.enabled_servers), len(self.visible_servers), datetime.datetime.now() - start))

    return results


  def GetHealthyPercentage(self):
    return (float(len(self.enabled_servers)) / float(len(self.visible_servers))) * 100    
    
  def RunHealthCheckThreads(self, checks, min_healthy_percent=MIN_HEALTHY_PERCENT):
    """Quickly ping nameservers to see which are healthy."""

    status_msg = 'Running initial health checks on %s servers' % len(self.enabled_servers)

    if self.thread_count > MAX_INITIAL_HEALTH_THREAD_COUNT:
      thread_count = MAX_INITIAL_HEALTH_THREAD_COUNT
    else:
      thread_count = self.thread_count

    try:
      results = self._LaunchQueryThreads('health', status_msg, list(self.enabled_servers),
                                         checks=checks, thread_count=thread_count)
    except ThreadFailure:
      self.msg("It looks like you couldn't handle %s threads, trying again with %s (slow)" % (thread_count, SLOW_MODE_THREAD_COUNT))
      self.thread_count = SLOW_MODE_THREAD_COUNT
      self.ResetTestResults()
      results = self._LaunchQueryThreads('ping', 'Checking nameserver availability', list(self.visible_servers))

    success_rate = self.GetHealthyPercentage()
    if success_rate < min_healthy_percent:
      self.msg('How odd! Only %0.1f percent of name servers are healthy. Trying again with %s threads (slow)'
               % (success_rate, SLOW_MODE_THREAD_COUNT))
      self.ResetTestResults()
      self.thread_count = SLOW_MODE_THREAD_COUNT
      time.sleep(5)
      results = self._LaunchQueryThreads('health', status_msg, list(self.enabled_servers),
                                         checks=checks, thread_count=thread_count)
    if self.enabled_servers:
      self.msg('%s of %s tested name servers are healthy' % (len(self.enabled_servers), len(self.visible_servers)))

    return results

  def RunFinalHealthCheckThreads(self, checks):
    """Quickly ping nameservers to see which are healthy."""
    status_msg = 'Running final health checks on %s servers' % len(self.enabled_servers)
    return self._LaunchQueryThreads('final', status_msg, list(self.enabled_servers), checks=checks)

  def RunCensorshipCheckThreads(self, checks):
    """Quickly ping nameservers to see which are healthy."""
    status_msg = 'Running censorship checks on %s servers' % len(self.enabled_servers)
    return self._LaunchQueryThreads('censorship', status_msg, list(self.enabled_servers), checks=checks)

  def RunPortBehaviorThreads(self):
    """Get port behavior data."""
    status_msg = 'Running port behavior checks on %s servers' % len(self.enabled_servers)
    return self._LaunchQueryThreads('port_behavior', status_msg, list(self.enabled_servers))

  def RunWildcardStoreThreads(self):
    """Store a wildcard cache value for all nameservers (using threads)."""
    status_msg = 'Waiting for wildcard cache queries from %s servers' % len(self.enabled_servers)
    return self._LaunchQueryThreads('store_wildcards', status_msg, list(self.enabled_servers))

