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

import operator
import os
import random
import pickle
import threading
import time
import tempfile
import sys
import Queue

# 3rd party libraries
import dns.resolver

import conn_quality
import nameserver
import util

NS_CACHE_SLACK = 2
CACHE_VER = 4

# How many nameservers get through the first ping to the health tests.
FIRST_CUT_MULTIPLIER = 0.10
PREFERRED_HEALTH_TIMEOUT_MULTIPLIER = 1.5
SYSTEM_HEALTH_TIMEOUT_MULTIPLIER = 2

# If we can't ping more than this, go into slowmode.
MIN_PINGABLE_PERCENT = 20
MIN_HEALTHY_PERCENT = 10
SLOW_MODE_THREAD_COUNT = 6

# Windows behaves in unfortunate ways if too many threads are specified
if sys.platform == "win32":
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
        if ns.disabled or other_ns.disabled:
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

        if ns.disabled:
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

  def __init__(self, nameservers, global_servers=None, regional_servers=None,
               num_servers=1,
               include_internal=False, threads=5, status_callback=None,
               timeout=5, health_timeout=5, ping_timeout=1,
               skip_cache_collusion_checks=False,
               ipv6_only=False):
    self.seen_ips = set()
    self.seen_names = set()
    self.timeout = timeout
    self.ping_timeout = ping_timeout
    self.num_servers = num_servers
    self.requested_health_timeout = health_timeout
    self.skip_cache_collusion_checks = skip_cache_collusion_checks
    self.health_timeout = health_timeout
    self.min_healthy_percent = MIN_HEALTHY_PERCENT
    self.status_callback = status_callback
    self.cache_dir = tempfile.gettempdir()
    self.ipv6_only = ipv6_only
    if threads > MAX_SANE_THREAD_COUNT:
      self.msg('Lowing thread count from %s to sane limit of %s' %
               (threads, MAX_SANE_THREAD_COUNT))
      self.thread_count = MAX_SANE_THREAD_COUNT
    else:
      self.thread_count = threads

    self.ApplyCongestionFactor()
    super(NameServers, self).__init__()
    self.system_nameservers = util.InternalNameServers()
    for (ip, name) in nameservers:
      self.AddServer(ip, name, is_custom=True, is_preferred=True)

    for (ip, name) in global_servers:
      self.AddServer(ip, name, is_global=True, is_preferred=True)

    for (ip, name) in regional_servers:
      self.AddServer(ip, name)

    if include_internal:
      for ip in self.system_nameservers:
        self.AddServer(ip, 'SYS-%s' % ip, is_preferred=True)

  @property
  def preferred(self):
    return [x for x in self if x.is_preferred]

  @property
  def enabled_preferred(self):
    return [x for x in self.preferred if not x.disabled]

  @property
  def secondaries(self):
    return [x for x in self if not x.is_preferred]

  @property
  def enabled_secondaries(self):
    return [x for x in self.secondaries if not x.disabled]

  @property
  def enabled(self):
    return [x for x in self if not x.disabled]

  @property
  def check_average(self):
    return util.CalculateListAverage([x.check_average for x in self if not x.disabled])

  def msg(self, msg, count=None, total=None, **kwargs):
    if self.status_callback:
      self.status_callback(msg, count=count, total=total, **kwargs)
    else:
      print '%s [%s/%s]' % (msg, count, total)

  def AddServer(self, ip, name, is_preferred=False, is_global=False, is_regional=False,
                is_custom=False):
    """Add a server to the list given an IP and name."""

    ns = nameserver.NameServer(ip, name=name, preferred=is_preferred)
    if self.ipv6_only and not ns.is_ipv6:
      return
    
    if ip in self.system_nameservers:
      ns.is_system = True
      ns.is_preferred = True
      ns.is_custom = False
      ns.system_position = self.system_nameservers.index(ip)

    ns.is_global = is_global
    ns.is_regional = is_regional
    ns.timeout = self.timeout
    ns.ping_timeout = self.ping_timeout
    # Give them a little extra love for the road.
    if ns.is_system:
      ns.health_timeout = self.health_timeout * SYSTEM_HEALTH_TIMEOUT_MULTIPLIER
      ns.ping_timeout = self.ping_timeout * SYSTEM_HEALTH_TIMEOUT_MULTIPLIER
    elif ns.is_preferred:
      ns.health_timeout = self.health_timeout * PREFERRED_HEALTH_TIMEOUT_MULTIPLIER
      ns.ping_timeout = self.ping_timeout * PREFERRED_HEALTH_TIMEOUT_MULTIPLIER
    else:
      ns.health_timeout = self.health_timeout
    self.append(ns)

  def append(self, ns):
    """Add a nameserver to the list, guaranteeing uniqueness."""
    if ns.ip in self.seen_ips:
      # Perhaps we already know of the IP, but do not have a proper name for it
      if ns.name != ns.ip:
        for existing_ns in self:
          if existing_ns.ip == ns.ip and existing_ns.name == existing_ns.ip:
            existing_ns.name = ns.name
      return None

    # Add an identifier to the name if necessary.
    if ns.name in self.seen_names:
      for identifier in range(2, 10):
        new_name = ''.join((ns.name, '-', str(identifier)))
        if new_name not in self.seen_names:
          ns.name = new_name
          break

#    print "Adding: %s [%s]" % (ns.name, ns.ip)
    super(NameServers, self).append(ns)
    self.seen_ips.add(ns.ip)
    self.seen_names.add(ns.name)

  def ApplyCongestionFactor(self):
    # If we are only benchmarking one server, don't bother w/ congestion checking.
    
    if len(self) == 1:
      return    
    cq = conn_quality.ConnectionQuality(status_callback=self.status_callback)
    (intercepted, congestion, multiplier) = cq.CheckConnectionQuality()[0:3]
    if intercepted:
      raise OutgoingUdpInterception(
          'Your router or Internet Service Provider appears to be intercepting '
          'and redirecting all outgoing DNS requests. This means you cannot '
          'benchmark or utilize alternate DNS servers. Please adjust your '
          'router configuration or file a support request with your ISP.'
      )
    if multiplier > 1:
# TODO(tstromberg): Consider retiring this feature for good.
#      self.timeout *= multiplier
      self.health_timeout *= multiplier
      self.ping_timeout *= multiplier
      self.msg('Applied %.2fX timeout multiplier due to congestion: %2.1f ping, %2.1f standard, %2.1f health.'
               % (multiplier, self.ping_timeout, self.timeout, self.health_timeout))

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

  def DisableUnwantedServers(self, target_count=None, delete_unwanted=False):
    """Given a target count, delete nameservers that we do not plan to test."""
    if not target_count:
      target_count = self.num_servers

    for ns in list(self.SortByFastest()):
      # If we have a specific target count to reach, we are in the first phase
      # of narrowing down nameservers. Silently drop bad nameservers.
      if ns.disabled and delete_unwanted and (ns.is_ipv6 or not ns.is_preferred):
        self.remove(ns)

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
      
      if not ns.is_preferred and not ns.disabled:
        if not secondaries_to_keep and secondaries_needed < 15:
          self.msg('%s appears to be the nearest regional (%0.2fms)' % (ns, ns.fastest_check_duration))
        secondaries_to_keep.append(ns)
#        print '| %s is near: %s (avg: %s)' % (ns, ns.fastest_check_duration, ns.check_average)
        if len(secondaries_to_keep) >= nearest_needed:
          break

    # Phase three is removing all of the slower secondary servers
    for ns in self.SortByFastest():
      if not ns.is_preferred and not ns.disabled and ns not in secondaries_to_keep:
#        print '| %s is fast: %s (lowest: %s)' % (ns, ns.check_average, ns.fastest_check_duration)
        secondaries_to_keep.append(ns)
        if len(secondaries_to_keep) == secondaries_needed:
          break

    for ns in self.secondaries:
      if ns not in secondaries_to_keep:
        self.remove(ns)

  def CheckHealth(self, primary_checks, secondary_checks, cache_dir=None, censor_tests=None):
    """Filter out unhealthy or slow replica servers."""
    if len(self) == 1:
      return None

    if cache_dir:
      self.cache_dir = cache_dir

    cpath = self._SecondaryCachePath()
    try:
      cached = self.InvokeSecondaryCache()
    except:
      self.msg('Failed to use secondary cache in [%s]: %s' % (cpath, util.GetLastExceptionString()))
      cached = False
    if not cached:
      self.msg('Building initial DNS cache for %s nameservers (%s threads)' %
               (len(self), self.thread_count))

    # If we have a lot of nameservers, make a first cut.
    if len(self) > (self.num_servers / FIRST_CUT_MULTIPLIER):
      self.PingNameServers()
      self.DisableUnwantedServers(target_count=int(len(self) * FIRST_CUT_MULTIPLIER),
                                  delete_unwanted=True)

#    for ns in self.SortByFastest():
#      print "%s: %s" % (ns, ns.check_average)
    self.RunHealthCheckThreads(primary_checks)
    self._DemoteSecondaryGlobalNameServers()
    self.DisableUnwantedServers(target_count=int(self.num_servers * NS_CACHE_SLACK),
                                delete_unwanted=True)
    if not cached:
      try:
        self._UpdateSecondaryCache(cpath)
      except:
        self.msg('Failed to save secondary cache in [%s]: %s' % (cpath, util.GetLastExceptionString()))

    if not self.skip_cache_collusion_checks:
      self.CheckCacheCollusion()
    self.DisableUnwantedServers()

    self.RunFinalHealthCheckThreads(secondary_checks)
    if censor_tests:
      self.RunCensorshipCheckThreads(censor_tests)
    else:
      # If we aren't doing censorship checks, quiet any possible false positives.
      self._RemoveGlobalWarnings()
    if not self.enabled:
      raise TooFewNameservers('None of the nameservers tested are healthy')

  def _RemoveGlobalWarnings(self):
    """If all nameservers have the same warning, remove it. It's likely false."""
    ns_count = len(self.enabled)
    seen_counts = {}

    # No sense in checking for duplicate warnings if we only have one server.
    if len(self.enabled) == 1:
      return
  
    for ns in self.enabled:
      for warning in ns.warnings:
        seen_counts[warning] = seen_counts.get(warning, 0) + 1

    for warning in seen_counts:
      if seen_counts[warning] == ns_count:
        self.msg('All nameservers have warning: %s (likely a false positive)' % warning)
        for ns in self.enabled:
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
#          ns.warnings.add('Alternate anycast address for %s' % provider)
        else:
          seen[provider]=ns

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
    return sorted(self, key=operator.attrgetter('check_average'))

  def SortByNearest(self):
    """Return a list of healthy servers in fastest-first order."""
    return sorted(self, key=operator.attrgetter('fastest_check_duration'))
  
  def ResetTestResults(self):
    """Reset the testng status of all disabled hosts."""
    return [ ns.ResetTestStatus() for ns in self ]

  def CheckCacheCollusion(self):
    """Mark if any nameservers share cache, especially if they are slower."""
    self.RunWildcardStoreThreads()
    sleepy_time = 4
    self.msg("Waiting %ss for TTL's to decrement." % sleepy_time)
    time.sleep(sleepy_time)

    test_combos = []
    good_nameservers = [x for x in self.SortByFastest() if not x.disabled]
    for (index, ns) in enumerate(good_nameservers):
      for compare_ns in good_nameservers:
        if ns != compare_ns:
          test_combos.append((compare_ns, ns))

    results = self.RunCacheCollusionThreads(test_combos)
    while not results.empty():
      (ns, shared_ns) = results.get()
      if shared_ns:
        ns.shared_with.add(shared_ns)
        shared_ns.shared_with.add(ns)
        if ns.disabled or shared_ns.disabled:
          continue

        if ns.check_average > shared_ns.check_average:
          slower = ns
          faster = shared_ns
        else:
          slower = shared_ns
          faster = ns

        if slower.system_position == 0:
          faster.disabled = 'Shares-cache with current primary DNS server'
          slower.warnings.add('Replica of %s' % faster.ip)
        elif slower.is_preferred and not faster.is_preferred:
          faster.disabled = 'Replica of %s [%s]' % (slower.name, slower.ip)
          slower.warnings.add('Replica of %s [%s]' % (faster.name, faster.ip))
        else:
          diff = slower.check_average - faster.check_average
          self.msg("Disabling %s - slower replica of %s by %0.1fms." % (slower.name_and_node, faster.name_and_node, diff))
          slower.disabled = 'Slower replica of %s [%s]' % (faster.name, faster.ip)
          faster.warnings.add('Replica of %s [%s]' % (slower.name, slower.ip))

  def _LaunchQueryThreads(self, action_type, status_message, items,
                          thread_count=None, **kwargs):
    """Launch query threads for a given action type.

    Args:
      action_type: a string describing an action type to pass
      status_message: Status to show during updates.
      items: A list of items to pass to the queue
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

    status_message = status_message + ' (%s threads)' % thread_count

    self.msg(status_message, count=0, total=len(items))
    for thread_num in range(0, thread_count):
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

    if not self.enabled:
      raise TooFewNameservers('None of the %s nameservers tested are healthy' % len(self))

    return results_queue

  def RunCacheCollusionThreads(self, test_combos):
    """Schedule and manage threading for cache collusion checks."""
    return self._LaunchQueryThreads('wildcard_check', 'Running cache-sharing checks on %s servers' % len(self.enabled), test_combos)

  def PingNameServers(self):
    """Quickly ping nameservers to see which are available."""
    try:
      results = self._LaunchQueryThreads('ping', 'Checking nameserver availability', list(self.enabled))
    except ThreadFailure:
      self.msg("It looks like you couldn't handle %s threads, trying again with %s (slow)" % (self.thread_count, SLOW_MODE_THREAD_COUNT))
      self.thread_count = SLOW_MODE_THREAD_COUNT
      self.ResetTestResults()
      results = self._LaunchQueryThreads('ping', 'Checking nameserver availability', list(self.enabled))

    success_rate = (float(len(self.enabled)) / float(len(self))) * 100
    if success_rate < MIN_PINGABLE_PERCENT:
      self.msg('How odd! Only %0.1f percent of name servers were pingable. Trying again with %s threads (slow)'
               % (success_rate, SLOW_MODE_THREAD_COUNT))
      self.ResetTestResults()
      self.thread_count = SLOW_MODE_THREAD_COUNT
      results = self._LaunchQueryThreads('ping', 'Checking nameserver availability', list(self))
    if self.enabled:
      success_rate = (float(len(self.enabled)) / float(len(self))) * 100
      self.msg('%s of %s tested name servers are available' %
               (len(self.enabled), len(self)))

  def RunHealthCheckThreads(self, checks):
    """Quickly ping nameservers to see which are healthy."""
    # Since we use this to decide which nameservers to include, cool down the thread
    # count a bit. 
    if self.thread_count > MAX_INITIAL_HEALTH_THREAD_COUNT:
      thread_count = MAX_INITIAL_HEALTH_THREAD_COUNT
    else:
      thread_count = self.thread_count

    try:
      results = self._LaunchQueryThreads('health', 'Running initial health checks on %s servers' % len(self.enabled),
                                         list(self.enabled), checks=checks, thread_count=thread_count)
    except ThreadFailure:
      self.msg("It looks like you couldn't handle %s threads, trying again with %s (slow)" % (thread_count, SLOW_MODE_THREAD_COUNT))
      self.thread_count = SLOW_MODE_THREAD_COUNT
      self.ResetTestResults()
      results = self._LaunchQueryThreads('ping', 'Checking nameserver availability', list(self))



    success_rate = (float(len(self.enabled)) / float(len(self))) * 100
    if success_rate < self.min_healthy_percent:
      self.msg('How odd! Only %0.1f percent of name servers are healthy. Trying again with %s threads (slow)'
               % (success_rate, SLOW_MODE_THREAD_COUNT))
      self.ResetTestResults()
      self.thread_count = SLOW_MODE_THREAD_COUNT
      time.sleep(5)
      results = self._LaunchQueryThreads('health', 'Running initial health checks on %s servers' % len(self.enabled),
                                         list(self.enabled), checks=checks, thread_count=thread_count)
    if self.enabled:
      success_rate = (float(len(self.enabled)) / float(len(self))) * 100
      self.msg('%s of %s tested name servers are healthy' %
               (len(self.enabled), len(self)))
               
  def RunFinalHealthCheckThreads(self, checks):
    """Quickly ping nameservers to see which are healthy."""
    results = self._LaunchQueryThreads('final', 'Running final health checks on %s servers' % len(self.enabled), list(self.enabled), checks=checks)

  def RunCensorshipCheckThreads(self, checks):
    """Quickly ping nameservers to see which are healthy."""
    results = self._LaunchQueryThreads('censorship', 'Running censorship checks on %s servers' % len(self.enabled), list(self.enabled), checks=checks)

  def RunPortBehaviorThreads(self):
    """Get port behavior data."""
    results = self._LaunchQueryThreads('port_behavior', 'Running port behavior checks on %s servers' % len(self.enabled), list(self.enabled))

  def RunWildcardStoreThreads(self):
    """Store a wildcard cache value for all nameservers (using threads)."""
    results = self._LaunchQueryThreads('store_wildcards', 'Waiting for wildcard cache queries from %s servers' % len(self.enabled), list(self.enabled))

