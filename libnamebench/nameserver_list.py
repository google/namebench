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
import Queue
import random
import sys
import threading
import time

# 3rd party libraries
import dns.resolver
import conn_quality
import addr_util
import nameserver
import util

NS_CACHE_SLACK = 2
CACHE_VER = 4


PREFERRED_HEALTH_TIMEOUT_MULTIPLIER = 1.5
SYSTEM_HEALTH_TIMEOUT_MULTIPLIER = 2
TOO_DISTANT_MULTIPLIER = 4.75

DEFAULT_MAX_SERVERS_TO_CHECK = 350


# If we can't ping more than this, go into slowmode.
MIN_PINGABLE_PERCENT = 5
MIN_HEALTHY_PERCENT = 10
SLOW_MODE_THREAD_COUNT = 6

# Windows behaves in unfortunate ways if too many threads are specified
DEFAULT_THREAD_COUNT = 35
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

  def __init__(self, thread_count=DEFAULT_THREAD_COUNT, max_servers_to_check=DEFAULT_MAX_SERVERS_TO_CHECK):
    self._ips = set()
    self.thread_count = thread_count 
    super(NameServers, self).__init__()

    self.client_latitude = None
    self.client_longitude = None
    self.client_country = None
    self.client_domain = None
    self.client_asn = None
    self.max_servers_to_check = max_servers_to_check

  @property
  def visible_servers(self):
    return [x for x in self if not x.is_hidden]

  @property
  def enabled_servers(self):
    return [x for x in self.visible_servers if not x.is_disabled]

  @property
  def disabled_servers(self):
    return [x for x in self.visible_servers if x.is_disabled]

  @property
  def enabled_keepers(self):
    return [x for x in self.enabled_servers if x.is_keeper]

  @property
  def enabled_supplemental(self):
    return [x for x in self.enabled_servers if not x.is_keeper]

  @property
  def supplemental_servers(self):
    return [x for x in self if not x.is_keeper]

  @property
  def country_servers(self):
    return [x for x in self if x.country_code == self.client_country]

  # Return a list of servers that match a particular tag
  def HasTag(self, tag):
    return [x for x in self if x.HasTag(tag)]

  # Return a list of servers that match a particular tag
  def HasVisibleTag(self, tag):
    return [x for x in self.visible_servers if x.HasTag(tag)]
    
  def SortEnabledByFastest(self):
    """Return a list of healthy servers in fastest-first order."""
    return sorted(self.enabled_servers, key=operator.attrgetter('check_average'))

  def SortEnabledByNearest(self):
    """Return a list of healthy servers in fastest-first order."""
    return sorted(self.enabled_servers, key=operator.attrgetter('fastest_check_duration'))

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
      existing_ns = self._GetObjectForIP(ns.ip)
      existing_ns.tags.update(ns.tags)
#      print "Adding tags for %s: %s" % (ns, ns.tags)
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

  def SetClientLocation(self, latitude, longitude, client_country):
    self.client_latitude = latitude
    self.client_longitude = longitude
    self.client_country = client_country

  def SetNetworkLocation(self, domain, asn):
    self.client_domain = domain
    self.client_asn = asn

  def FilterByTag(self, include_tags=None, require_tags=None):
    for ns in self:
      if include_tags:
        if not ns.MatchesTags(include_tags):
          ns.is_hidden = True
      if require_tags:
        for tag in require_tags:
          if not ns.HasTag(tag):
            ns.is_hidden = True
    if not self.enabled_servers:
      raise TooFewNameservers('No nameservers specified matched tags %s %s' % (include_tags, require_tags))

    if require_tags:
      self.msg("%s of %s nameservers have tags: %s (%s required)" %
               (len(self.visible_servers), len(self), ', '.join(include_tags),
                ', '.join(require_tags)))
    else:
      self.msg("%s of %s nameservers have tags: %s" %
               (len(self.visible_servers), len(self), ', '.join(include_tags)))

  def HasEnoughInCountryServers():
    return len(self.country_servers) > self.max_servers_to_check

  def NearbyServers(self, max_distance):
    srv_by_dist = sorted([(x.DistanceFromCoordinates(self.client_latitude, self.client_longitude), x)
                          for x in self.HasVisibleTag('regional')], key=operator.itemgetter(0))
    for distance, ns in srv_by_dist:
      if distance < float(max_distance):
        yield ns

  def AddNetworkTags(self):
    """Add network tags for each nameserver."""
    if self.client_domain:
      provider = self.client_domain.split('.')[0]
    else:
      provider = None
      
    for ns in self:
      ns.AddNetworkTags(self.client_domain, provider, self.client_asn, self.client_country)


  def AddLocalityTags(self, max_distance):
    if self.client_latitude:
      count = 0
      for ns in self.NearbyServers(max_distance):
        count += 1
        if count > self.max_servers_to_check:
          break
        ns.tags.add('nearby')
  
  def DisableSlowestSupplementalServers(self, multiplier=TOO_DISTANT_MULTIPLIER, max_servers=None,
                                        prefer_asn=None):
    """Disable servers who's fastest duration is multiplier * average of best 10 servers."""
    if not max_servers:
      max_servers = self.max_servers_to_check

    supplemental_servers = self.enabled_supplemental
    fastest = [x for x in self.SortEnabledByFastest()][:10]
    best_10 = util.CalculateListAverage([x.fastest_check_duration for x in fastest])
    cutoff = best_10 * multiplier
    self.msg("Removing secondary nameservers slower than %0.2fms (max=%s)" % (cutoff, max_servers))
    
    for (idx, ns) in enumerate(self.SortEnabledByFastest()):
      hide = False
      if ns not in supplemental_servers:
        continue
    
      if ns.fastest_check_duration > cutoff:
        hide = True
      if idx > max_servers:
        hide = True

      if hide:
        matches = ns.MatchesTags(nameserver.PROVIDER_TAGS)
        if matches:
          self.msg("%s seems slow, but has tag: %s" % (ns, matches))
        else:
          ns.is_hidden = True

  def _FastestByLocalProvider(self):
    """Find the fastest DNS server by the client provider."""
    fastest =  self.SortEnabledByFastest()

    # Give preference in tag order
    for tag in nameserver.PROVIDER_TAGS:
      for ns in fastest:
        if ns.HasTag(tag):
          return ns
        
  def HideBrokenIPV6Servers(self):
    """Most people don't care about these."""
    
    for ns in self.disabled_servers:
      if ns.HasTag('ipv6') and not ns.is_hidden:
        ns.is_hidden = True

  def HideSlowSupplementalServers(self, target_count):
    """Given a target count, delete nameservers that we do not plan to test."""
    # Magic secondary mixing algorithm:
    # - Half of them should be the "nearest" nameservers
    # - Half of them should be the "fastest average" nameservers
    self.msg("Hiding all but %s servers" % target_count)
    keepers = self.enabled_keepers
    isp_keeper = self._FastestByLocalProvider()
    if isp_keeper:
      self.msg("%s is the fastest DNS server provided by your ISP." % isp_keeper)
      keepers.append(isp_keeper)

    supplemental_servers_needed = target_count - len(keepers)
    if supplemental_servers_needed < 1 or not self.enabled_supplemental:
      return
    nearest_needed = int(supplemental_servers_needed / 2.0)

    if supplemental_servers_needed < 50:
      self.msg("Picking %s secondary servers to use (%s nearest, %s fastest)" %
               (supplemental_servers_needed, nearest_needed, supplemental_servers_needed - nearest_needed))

    # Phase two is picking the nearest secondary server
    supplemental_servers_to_keep = []
    for ns in self.SortEnabledByNearest():
      if ns not in keepers:
        if not supplemental_servers_to_keep and supplemental_servers_needed < 15:
          self.msg('%s appears to be the nearest regional (%0.2fms)' % (ns, ns.fastest_check_duration))
        supplemental_servers_to_keep.append(ns)
        if len(supplemental_servers_to_keep) >= nearest_needed:
          break

    # Phase three is hiding the slower secondary servers
    for ns in self.SortEnabledByFastest():
      if ns not in keepers and ns not in supplemental_servers_to_keep:
        supplemental_servers_to_keep.append(ns)
        if len(supplemental_servers_to_keep) >= supplemental_servers_needed:
          break

    for ns in self.supplemental_servers:
      if ns not in supplemental_servers_to_keep and ns not in keepers:
        ns.is_hidden = True

  def CheckHealth(self, sanity_checks=None, max_servers=11, prefer_asn=None):
    """Filter out unhealthy or slow replica servers."""
    self.PingNameServers()
    if len(self.enabled_servers) > max_servers:
      self.DisableSlowestSupplementalServers(prefer_asn=prefer_asn)
    self.RunHealthCheckThreads(sanity_checks['primary'])
    if len(self.enabled_servers) > max_servers:
      self._DemoteSecondaryGlobalNameServers()
      self.HideSlowSupplementalServers(int(max_servers * NS_CACHE_SLACK))
    # TODO(tstromberg): Insert caching here.
    if len(self.enabled_servers) > 1:
      self.CheckCacheCollusion()
      self.HideSlowSupplementalServers(max_servers)

    self.RunFinalHealthCheckThreads(sanity_checks['secondary'])
    self.HideBrokenIPV6Servers()
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
    for ns in self.SortEnabledByFastest():
      if ns.MatchesTags(['preferred', 'global']):
        if ns.provider in seen and not ns.MatchesTags(['system', 'specified']):
          faster_ns = seen[ns.provider]
          if ns.HasTag('preferred'):
            self.msg('Making %s the primary anycast - faster than %s by %2.2fms' %
                     (faster_ns.name_and_node, ns.name_and_node, ns.check_average - faster_ns.check_average))
          ns.is_hidden = True
        else:
          seen[ns.provider] = ns

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
    good_nameservers = [x for x in self.SortEnabledByFastest()]
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
          faster.DisableWithMessage('Shares-cache with current primary DNS server')
          slower.warnings.add('Replica of %s' % faster.ip)
        elif slower.is_keeper and not faster.is_keeper:
          faster.DisableWithMessage('Replica of %s [%s]' % (slower.name, slower.ip))
          slower.warnings.add('Replica of %s [%s]' % (faster.name, faster.ip))
        else:
          diff = slower.check_average - faster.check_average
          self.msg("Disabling %s - slower replica of %s by %0.1fms." % (slower.name_and_node, faster.name_and_node, diff))
          slower.DisableWithMessage('Slower replica of %s [%s]' % (faster.name, faster.ip))
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
    test_servers = list(self.enabled_servers)
    try:
      results = self._LaunchQueryThreads('ping', 'Checking nameserver availability', test_servers)
    except ThreadFailure:
      self.msg("It looks like you couldn't handle %s threads, trying again with %s (slow)" % (self.thread_count, SLOW_MODE_THREAD_COUNT))
      self.thread_count = SLOW_MODE_THREAD_COUNT
      self.ResetTestResults()
      results = self._LaunchQueryThreads('ping', 'Checking nameserver availability', test_servers)

    success_rate = self.GetHealthyPercentage(compare_to=test_servers)
    if success_rate < MIN_PINGABLE_PERCENT:
      self.msg('How odd! Only %0.1f percent of name servers were pingable. Trying again with %s threads (slow)'
               % (success_rate, SLOW_MODE_THREAD_COUNT))
      self.ResetTestResults()
      self.thread_count = SLOW_MODE_THREAD_COUNT
      results = self._LaunchQueryThreads('ping', 'Checking nameserver availability', test_servers)
    if self.enabled_servers:
      self.msg('%s of %s servers are available (duration: %s)' %
               (len(self.enabled_servers), len(test_servers), datetime.datetime.now() - start))
    return results


  def GetHealthyPercentage(self, compare_to=None):
    if not compare_to:
      compare_to = self.visible_servers
    return (float(len(self.enabled_servers)) / float(len(compare_to))) * 100

  def RunHealthCheckThreads(self, checks, min_healthy_percent=MIN_HEALTHY_PERCENT):
    """Quickly ping nameservers to see which are healthy."""

    test_servers = self.enabled_servers
    status_msg = 'Running initial health checks on %s servers' % len(test_servers)

    if self.thread_count > MAX_INITIAL_HEALTH_THREAD_COUNT:
      thread_count = MAX_INITIAL_HEALTH_THREAD_COUNT
    else:
      thread_count = self.thread_count

    try:
      results = self._LaunchQueryThreads('health', status_msg, test_servers,
                                         checks=checks, thread_count=thread_count)
    except ThreadFailure:
      self.msg("It looks like you couldn't handle %s threads, trying again with %s (slow)" % (thread_count, SLOW_MODE_THREAD_COUNT))
      self.thread_count = SLOW_MODE_THREAD_COUNT
      self.ResetTestResults()
      results = self._LaunchQueryThreads('ping', 'Checking nameserver availability', list(self.visible_servers))

    success_rate = self.GetHealthyPercentage(compare_to=test_servers)
    if success_rate < min_healthy_percent:
      self.msg('How odd! Only %0.1f percent of name servers are healthy. Trying again with %s threads (slow)'
               % (success_rate, SLOW_MODE_THREAD_COUNT))
      self.ResetTestResults()
      self.thread_count = SLOW_MODE_THREAD_COUNT
      time.sleep(5)
      results = self._LaunchQueryThreads('health', status_msg, test_servers,
                                         checks=checks, thread_count=thread_count)
    self.msg('%s of %s tested name servers are healthy' %
             (len(self.enabled_servers), len(test_servers)))
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

