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
CACHE_VER = 3
MAX_CONGESTION_MULTIPLIER = 2.5
FIRST_CUT_MULTIPLIER = 0.18
GLOBAL_HEALTH_TIMEOUT_MULTIPLIER = 1.5
SYSTEM_HEALTH_TIMEOUT_MULTIPLIER = 2


# Windows behaves in unfortunate ways if too many threads are specified
if sys.platform == "win32":
  MAX_SANE_THREAD_COUNT = 60
else:
  MAX_SANE_THREAD_COUNT = 250

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

class QueryThreads(threading.Thread):
  """Quickly see which nameservers are awake."""
  def __init__(self, input_queue, results_queue, action_type, checks=None):
    threading.Thread.__init__(self)
    self.input = input_queue
    self.action_type = action_type
    self.results = results_queue
    self.checks = checks
  
  def run(self):
    """Iterate over the queue, processing each item."""
    while not self.input.empty():
      # check_wildcards is special: it has a tuple of two nameservers
      if self.action_type == 'wildcard_check':
        (ns, other_ns) = self.input.get_nowait()
        if ns.disabled or other_ns.disabled:
          self.results.put(None)
          continue
        else:
          self.results.put((ns, ns.TestSharedCache(other_ns)))
      # everything else only has a single nameserver.
      else:
        try:
          ns = self.input.get_nowait()
          if ns.disabled:
            self.results.put(None)
            continue
          if self.action_type == 'ping':
            self.results.put(ns.CheckHealth(fast_check=True))
          elif self.action_type == 'health':
            self.results.put(ns.CheckHealth(sanity_checks=self.checks))
          elif self.action_type == 'store_wildcards':
            self.results.put(ns.StoreWildcardCache())
          else:
            raise ValueError('Invalid action type: %s' % self.action_type)
        except Queue.Empty:
          pass

class NameServers(list):

  def __init__(self, nameservers, secondary=None, num_servers=1,
               include_internal=False, threads=20, status_callback=None,
               timeout=5, health_timeout=5, skip_cache_collusion_checks=False):
    self.seen_ips = set()
    self.seen_names = set()
    self.timeout = timeout
    self.num_servers = num_servers
    self.requested_health_timeout = health_timeout
    self.skip_cache_collusion_checks = skip_cache_collusion_checks
    self.health_timeout = health_timeout
    self.status_callback = status_callback
    self.cache_dir = tempfile.gettempdir()
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
      self.AddServer(ip, name, primary=True)

    if secondary:
      for (ip, name) in secondary:
        self.AddServer(ip, name, primary=False)

    if include_internal:
      for ip in self.system_nameservers:
        self.AddServer(ip, 'SYS-%s' % ip, primary=True)


  @property
  def primaries(self):
    return [x for x in self if x.is_primary]

  @property
  def enabled_primaries(self):
    return [x for x in self.primaries if not x.disabled]

  @property
  def secondaries(self):
    return [x for x in self if not x.is_primary]

  @property
  def enabled_secondaries(self):
    return [x for x in self.secondaries if not x.disabled]

  @property
  def enabled(self):
    return [x for x in self if not x.disabled]
    
  def msg(self, msg, count=None, total=None, **kwargs):
    if self.status_callback:
      self.status_callback(msg, count=count, total=total, **kwargs)
    else:
      print '%s [%s/%s]' % (msg, count, total)

  def AddServer(self, ip, name, primary=False):
    """Add a server to the list given an IP and name."""

    ns = nameserver.NameServer(ip, name=name, primary=primary)
    if ip in self.system_nameservers:
      ns.is_system = True
      ns.is_primary = True
      ns.system_position = self.system_nameservers.index(ip)

    ns.timeout = self.timeout
    # Give them a little extra love for the road.
    if ns.is_system:
      ns.health_timeout = self.health_timeout * SYSTEM_HEALTH_TIMEOUT_MULTIPLIER
    elif ns.is_primary:
      ns.health_timeout = self.health_timeout * GLOBAL_HEALTH_TIMEOUT_MULTIPLIER
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
    cq = conn_quality.ConnectionQuality(status_callback=self.status_callback)
    (intercepted, congestion, multiplier) = cq.CheckConnectionQuality()[0:3] 
    if intercepted:
      raise OutgoingUdpInterception(
          'Your Internet Service Provider appears to be intercepting and '
          'redirecting all outgoing DNS requests. This means we cannot '
          'benchmark or utilize alternate DNS servers. Please ask them to stop.'
      )
    if multiplier > 1:
      self.timeout *= multiplier
      self.health_timeout *= multiplier
      self.msg('Applied %.2fX timeout multiplier due to congestion: %2.1f standard, %2.1f health.'
               % (multiplier, self.timeout, self.health_timeout))


  def InvokeSecondaryCache(self):
    cached = False
    if self.cache_dir:
      cpath = self._SecondaryCachePath()
      cache_data = self._LoadSecondaryCache(cpath)
      if cache_data:
        for ns in self:
          ns.warnings = set()
          ns.checks = []
        cached = True
        cached_ips = [x.ip for x in cache_data if not x.is_primary]
        for ns in list(self.secondaries):
          if ns.ip not in cached_ips:
            self.remove(ns)
    return cached

  def DisableUnwantedServers(self, target_count=None, delete_unwanted=False):
    if not target_count:
      target_count = self.num_servers

    for ns in list(self.SortByFastest()):
      # If we have a specific target count to reach, we are in the first phase
      # of narrowing down nameservers. Silently drop bad nameservers.
      if ns.disabled and delete_unwanted and not ns.is_primary:
        print "Disabled %s (disabled)" % ns
        self.remove(ns)

    primary_count = len(self.enabled_primaries)
    secondaries_kept = 0
    secondaries_needed = target_count - primary_count

    # Phase two is removing all of the slower secondary servers
    for (idx, ns) in enumerate(list(self.SortByFastest())):
      if not ns.is_primary and not ns.disabled:
        if secondaries_kept >= secondaries_needed:
          # Silently remove secondaries who's only fault was being too slow.
          print "%s: %s did not make the %s cut: %s [%s]" % (idx, ns, secondaries_needed, ns.check_average, len(ns.checks))
          self.remove(ns)
        else:
          secondaries_kept += 1

  def CheckHealth(self, cache_dir=None, sanity_checks=None):
    """Filter out unhealthy or slow replica servers."""
    if len(self) == 1:
      return None

    if cache_dir:
      self.cache_dir = cache_dir

    cpath = self._SecondaryCachePath()
    cached = self.InvokeSecondaryCache()
    if not cached:
      self.msg('Building initial DNS cache for %s nameservers [%s threads]' %
               (len(self), self.thread_count))

    # If we have a lot of nameservers, make a first cut.
    if len(self) > (self.num_servers / FIRST_CUT_MULTIPLIER):
      self.PingNameServers()
      self.DisableUnwantedServers(target_count=len(self) * FIRST_CUT_MULTIPLIER,
                                  delete_unwanted=True)

    self.RunHealthCheckThreads(sanity_checks=sanity_checks)
    self.DisableUnwantedServers(target_count=int(self.num_servers * NS_CACHE_SLACK),
                                delete_unwanted=True)
    if not cached:
      self._UpdateSecondaryCache(cpath)

    if not self.skip_cache_collusion_checks:
      self.CheckCacheCollusion()
    self.DisableUnwantedServers()

    if not self.enabled:
      raise TooFewNameservers('None of the nameservers tested are healthy')

  def _SecondaryCachePath(self):
    """Find a usable and unique location to store health results."""
    secondary_ips = [x.ip for x in self.secondaries]
    checksum = hash(str(sorted(secondary_ips)))
    basefile = '.'.join(map(str, ('namebench', CACHE_VER, len(secondary_ips),
                                  '_'.join(self.system_nameservers),
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
      self.msg('Loading local server health cache: %s' % cpath)
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
                
        if ns.check_average > shared_ns.check_average:
          slower = ns
          faster = shared_ns
        else:
          slower = shared_ns
          faster = ns
        
        if slower.system_position == 0:
          faster.disabled = 'Shares-cache with current primary DNS server'
          slower.warnings.add('Replica of faster %s' % faster.ip)
        elif slower.is_primary and not faster.is_primary:
          faster.disabled = 'Replica of %s [%s]' % (slower.name, slower.ip)
          slower.warnings.add('Replica of %s [%s]' % (faster.name, faster.ip))
        else:
          slower.disabled = 'Slower replica of %s [%s]' % (faster.name, faster.ip)
          faster.warnings.add('Replica of %s [%s]' % (slower.name, slower.ip))

  def _LaunchQueryThreads(self, action_type, status_message, items, **kwargs):
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
    
    thread_count = self.thread_count
    if thread_count > len(items):
      thread_count = len(items)
  
    self.msg(status_message, count=0, total=len(items))
    for thread_num in range(0, thread_count):
      thread = QueryThreads(input_queue, results_queue, action_type, **kwargs)
      thread.start()
      threads.append(thread)

    while results_queue.qsize() != len(items):
      self.msg(status_message, count=results_queue.qsize(), total=len(items))
      time.sleep(0.1)

    self.msg(status_message, count=results_queue.qsize(), total=len(items))
    for thread in threads:
      thread.join()

    if not self.enabled:
      raise TooFewNameservers('None of the %s nameservers tested are healthy' % len(self))

    return results_queue


  def RunCacheCollusionThreads(self, test_combos):
    """Schedule and manage threading for cache collusion checks."""
    return self._LaunchQueryThreads('wildcard_check', 'Waiting for cache collusion checks', test_combos)

  def PingNameServers(self):
    """Quickly ping nameservers to see which are available."""
    results = self._LaunchQueryThreads('ping', 'Checking nameserver availability', list(self))
    if self.enabled:
      self.msg('%s of %s name servers are available' % (len(self.enabled), len(self)))

  def RunHealthCheckThreads(self, fast_check=False, sanity_checks=None):
    """Quickly ping nameservers to see which are healthy."""
    results = self._LaunchQueryThreads('health', 'Checking nameserver health', list(self), checks=sanity_checks)
    if self.enabled:
      self.msg('%s of %s name servers are healthy' % (len(self.enabled), len(self)))

  def RunWildcardStoreThreads(self):
    """Store a wildcard cache value for all nameservers (using threads)."""
    results = self._LaunchQueryThreads('store_wildcards', 'Waiting for initial cache check threads', list(self))
    if self.enabled:
      self.msg('%s of %s name servers are healthy' % (len(self.enabled), len(self)))
    
