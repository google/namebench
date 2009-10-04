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
import pickle
import threading
import time

import dns.resolver
import nameserver
import util

NS_CACHE_SLACK = 1.6
CACHE_VERSION = 1
MAX_CONGESTION_MULTIPLIER = 4

class TestNameServersThread(threading.Thread):
  """Quickly test the health of many nameservers with multiple threads."""

  def __init__(self, nameservers, compare_cache=None):
    threading.Thread.__init__(self)
    self.compare_cache = compare_cache
    self.nameservers = nameservers
    self.results = []

  def run(self):
    for ns in self.nameservers:
      if self.compare_cache:
        self.results.append(ns.TestSharedCache(self.compare_cache))
      else:
        self.results.append(ns.CheckHealth())


class NameServers(list):

  def __init__(self, nameservers, secondary=None, num_servers=1,
               include_internal=False, threads=20, cache_dir=None,
               timeout=None, health_timeout=None):
    self.seen_ips = set()
    self.seen_names = set()
    self.thread_count = threads
    self.timeout = timeout
    self.num_servers = num_servers
    self.requested_health_timeout = health_timeout
    self.health_timeout = health_timeout
    self.cache_dir = cache_dir

    super(NameServers, self).__init__()
    for (ip, name) in nameservers:
      self.AddServer(ip, name, primary=True)

    if secondary:
      for (ip, name) in secondary:
        self.AddServer(ip, name, primary=False)

    if include_internal:
      for ip in self.InternalNameServers():
        self.AddServer(ip, 'SYS-%s' % ip, internal=True, primary=True)

  @property
  def primaries(self):
    return [x for x in self if x.is_primary]
    
  @property
  def secondaries(self):
    return [x for x in self if not x.is_primary]

  def AddServer(self, ip, name, primary=False, internal=False):
    """Add a server to the list given an IP and name."""
    ns = nameserver.NameServer(ip, name=name, primary=primary,
                               internal=internal)
    ns.timeout = self.timeout
    if primary or internal:
      ns.health_timeout *= 1.2
    else:
      ns.health_timeout = self.health_timeout
    self.append(ns)

  def append(self, ns):
    """Add a nameserver to the list, guaranteeing uniqueness."""
    if ns.ip in self.seen_ips:
      return None

    # Add an identifier to the name if necessary.
    if ns.name in self.seen_names:
      for identifier in range(2, 10):
        new_name = ''.join((ns.name, '-', str(identifier)))
        if new_name not in self.seen_names:
          ns.name = new_name
          break

    super(NameServers, self).append(ns)
    self.seen_ips.add(ns.ip)
    self.seen_names.add(ns.name)

  def ApplyCongestionFactor(self, multiplier):
    if multiplier > MAX_CONGESTION_MULTIPLIER:
      multiplier = MAX_CONGESTION_MULTIPLIER
    self.timeout *= multiplier
    self.health_timeout *= multiplier
    print ('* General timeout is now %.1fs, Health timeout is now %.1fs' %
           (self.timeout, self.health_timeout))

  def InvokeSecondaryCache(self):
    cached = False
    if self.cache_dir:
      cpath = self._SecondaryCachePath()
      cache_data = self._LoadSecondaryCache(cpath)
      if cache_data:
        cached = True
        cached_ips = [x.ip for x in cache_data if not x.is_primary]
#        print "- %s awesome secondaries loaded from cache." % len(cache_data)
        for ns in list(self.secondaries):
          if ns.ip not in cached_ips:
            self.remove(ns) 
    return cached
      
  def RemoveUndesirables(self, target_count=None):
    if not target_count:
      target_count = self.num_servers      
    
    # Phase one is removing all of the unhealthy servers
    for ns in list(self.SortByFastest()):
      if not ns.is_healthy:
#        print "- Removing %s (unhealthy)" % ns
        self.remove(ns)
      elif ns.is_slower_replica:
        print "- Removing %s (slow replica)" % ns
        self.remove(ns)

    primary_count = len(self.primaries)
    secondaries_kept = 0
    secondaries_needed = target_count - primary_count
#    print "- We need %s secondaries to get to %s total" % (secondaries_needed, target_count)
        
    # Phase two is removing all of the slower secondary servers
    for ns in list(self.SortByFastest()):
      if not ns.is_primary:
        if secondaries_kept >= secondaries_needed:
#          print "- Removing %s (slower secondary: %sms)" % (ns, ns.check_duration)
          self.remove(ns)
        else:
#          print '- Keeping %s (fast secondary: %sms)' % (ns, ns.check_duration)
          secondaries_kept += 1

  def FindAndRemoveUndesirables(self):
    """Filter out unhealthy or slow replica servers."""
    print("- Considering %s primary and %s secondary servers for benchmarking." %
          (len(self.primaries), len(self.secondaries)))
    cpath = self._SecondaryCachePath()
    cached = self.InvokeSecondaryCache()    
    if not cached:
      print('- Building initial DNS cache for %s nameservers [%s threads]' %
            (len(self), self.thread_count))
    else:
      print '- Checking the health of %s nameservers' % len(self)
    self.RunHealthCheckThreads()
    self.RemoveUndesirables(target_count=int(self.num_servers * NS_CACHE_SLACK))
    if not cached:
      self._UpdateSecondaryCache(cpath)
    
    print '- Checking for slow replicas among %s nameservers' % len(self)
    self.CheckCacheCollusion()
    self.RemoveUndesirables()

  def _SecondaryCachePath(self):
    """Find a usable and unique location to store health results."""
    secondary_ips = [x.ip for x in self.secondaries]
    checksum = hash(str(sorted(secondary_ips)))
    return '%s/namebench.%s.%s.%0f.%s' % (self.cache_dir, CACHE_VERSION,
                                          len(secondary_ips),
                                          self.requested_health_timeout,
                                          checksum)

  def _LoadSecondaryCache(self, cpath):
    """Check if our health cache has any good data."""
    if os.path.exists(cpath) and os.path.isfile(cpath):
      print '- Loading local server health cache: %s' % cpath
      cf = open(cpath, 'r')
      try:
        return pickle.load(cf)
      except EOFError:
        print '- No usable data in %s' % cpath
    return False

  def _UpdateSecondaryCache(self, cpath):
    """Update the cache with our object."""
    cf = open(cpath, 'w')
    try:
      pickle.dump(self, cf)
    except TypeError, exc:
      print '* Could not save cache: %s' % exc

  def InternalNameServers(self):
    """Return list of DNS server IP's used by the host."""
    return dns.resolver.Resolver().nameservers

  def SortByFastest(self):
    """Return a list of healthy servers in fastest-first order."""
    return sorted(self, key=operator.attrgetter('check_duration'))

  def CheckCacheCollusion(self):
    """Mark if any nameservers share cache, especially if they are slower."""

    # Give the TTL a chance to decrement
    time.sleep(5)
    tested = []
    ns_by_fastest = self.SortByFastest()

    for other_ns in ns_by_fastest:
      test_servers = []
      for ns in ns_by_fastest:
        if ns.ip == other_ns.ip or ns in other_ns.shared_with:
          continue
        elif (ns.ip, other_ns.ip) in tested or (other_ns.ip, ns.ip) in tested:
          continue
        test_servers.append(ns)
        tested.append((ns.ip, other_ns.ip))

      self.RunCacheCollusionThreads(other_ns, test_servers)

  def RunCacheCollusionThreads(self, other_ns, test_servers):
    """Schedule and manage threading for cache collusion checks."""
    threads = []
    # TODO(tstromberg): This should be split per-test rather than per-server,
    # to reduce the chance of eliminating servers just because a user began
    # to download something in the background.
    for chunk in util.SplitSequence(test_servers, self.thread_count):
      thread = TestNameServersThread(chunk, compare_cache=other_ns)
      thread.start()
      threads.append(thread)

    results = []
    for thread in threads:
      thread.join()
      results.extend(thread.results)

    # To avoid concurrancy issues, we don't modify the other ns in the thread.
    for (shared, slower, faster) in results:
      if shared:
        dur_delta = abs(slower.check_duration - faster.check_duration)
        print ('  * %s is a slower replica of %s (%sms slower)' %
               (slower, faster, dur_delta))
        slower.warnings.append('shares cache with %s' % faster.ip)
        faster.warnings.append('shares cache with %s' % slower.ip)
        slower.shared_with.append(faster)
        faster.shared_with.append(slower)
        slower.is_slower_replica = True

  def RunHealthCheckThreads(self):
    """Check the health of all of the nameservers (using threads)."""
    threads = []
    for chunk in util.SplitSequence(self, self.thread_count):
      thread = TestNameServersThread(chunk)
      thread.start()
      threads.append(thread)
    for thread in threads:
      thread.join()
