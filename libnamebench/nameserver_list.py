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

# 3rd party libraries
import dns.resolver

import conn_quality
import nameserver
import util

NS_CACHE_SLACK = 1.7
CACHE_VER = 2
MAX_CONGESTION_MULTIPLIER = 5
PRIMARY_HEALTH_TIMEOUT_MULTIPLIER = 3


# Windows behaves in unfortunate ways if too many threads are specified
if sys.platform == "win32":
  MAX_SANE_THREAD_COUNT = 60
else:
  MAX_SANE_THREAD_COUNT = 90

class OutgoingUdpInterception(Exception):

  def __init__(self, value):
    self.value = value

  def __str__(self):
    return repr(self.value)


class TestNameServersThread(threading.Thread):
  """Quickly test the health of many nameservers with multiple threads."""

  def __init__(self, nameservers, store_wildcard=False, compare_cache=None):
    threading.Thread.__init__(self)
    self.store_wildcard = store_wildcard
    self.compare_cache = compare_cache
    self.nameservers = nameservers
    self.results = []

  def run(self):
    sys.stdout.flush()
    for ns in self.nameservers:
      if ns.disabled:
        continue
      if self.store_wildcard:
        self.results.append(ns.StoreWildcardCache())
      elif self.compare_cache:
        self.results.append(ns.TestSharedCache(self.compare_cache))
      else:
        self.results.append(ns.CheckHealth())


class NameServers(list):

  def __init__(self, nameservers, secondary=None, num_servers=1,
               include_internal=False, threads=20, status_callback=None,
               timeout=5, health_timeout=5):
    self.seen_ips = set()
    self.seen_names = set()
    self.timeout = timeout
    self.num_servers = num_servers
    self.requested_health_timeout = health_timeout
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

  def msg(self, msg, count=None, total=None, error=False):
    if self.status_callback:
      self.status_callback(msg, count=count, total=total, error=error)
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
    if ns.is_primary:
      ns.health_timeout = self.health_timeout * PRIMARY_HEALTH_TIMEOUT_MULTIPLIER
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
    self.msg('Checking connection quality...')
    cq = conn_quality.ConnectionQuality()
    (intercepted, congestion, duration) = cq.CheckConnectionQuality()
    if intercepted:
      raise OutgoingUdpInterception(
          'Your Internet Service Provider appears to be intercepting and '
          'redirecting all outgoing DNS requests. This means we cannot '
          'benchmark or utilize alternate DNS servers. Please ask them to stop.'
      )
    if congestion > 1:
      if congestion > MAX_CONGESTION_MULTIPLIER:
        multiplier = MAX_CONGESTION_MULTIPLIER
      else:
        multiplier = congestion

      self.timeout *= multiplier
      self.health_timeout *= multiplier
      self.msg('Congestion detected. Applied %.2f multiplier to timeouts'
               % multiplier)
    else:
      self.msg('Connection appears healthy (latency %.2fms)' % duration)


  def InvokeSecondaryCache(self):
    cached = False
    if self.cache_dir:
      cpath = self._SecondaryCachePath()
      cache_data = self._LoadSecondaryCache(cpath)
      if cache_data:
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
        self.remove(ns)

    primary_count = len(self.enabled_primaries)
    secondaries_kept = 0
    secondaries_needed = target_count - primary_count

    # Phase two is removing all of the slower secondary servers
    for ns in list(self.SortByFastest()):
      if not ns.is_primary and not ns.disabled:
        if secondaries_kept >= secondaries_needed:
          # Silently remove secondaries who's only fault was being too slow.
          self.remove(ns)
        else:
          secondaries_kept += 1

  def CheckHealth(self, cache_dir=None):
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
    self.RunHealthCheckThreads()
    self.DisableUnwantedServers(target_count=int(self.num_servers * NS_CACHE_SLACK),
                                delete_unwanted=True)
    if not cached:
      self._UpdateSecondaryCache(cpath)

    self.CheckCacheCollusion()
    self.DisableUnwantedServers()

  def _SecondaryCachePath(self):
    """Find a usable and unique location to store health results."""
    secondary_ips = [x.ip for x in self.secondaries]
    checksum = hash(str(sorted(secondary_ips)))
    basefile = '.'.join(map(str, ('namebench', CACHE_VER, len(secondary_ips),
                                  self.num_servers,
                                  self.requested_health_timeout, checksum)))
    return os.path.join(self.cache_dir, basefile)

  def InvalidateSecondaryCache(self):
    cpath = self._SecondaryCachePath()
    if os.path.exists(cpath):
      self.msg('Invalidating cache in %s' % cpath)
      os.unlink(cpath)
    else:
      self.msg('Cache not found in %s to invalidate' % cpath)

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
    return sorted(self, key=operator.attrgetter('check_duration'))

  def CheckCacheCollusion(self):
    """Mark if any nameservers share cache, especially if they are slower."""
    self.RunWildcardStoreThreads()
    # Give the TTL a chance to decrement
    self.msg("Waiting for nameservers TTL's to decrement")
    time.sleep(4)
    tested = []
    ns_by_fastest = [x for x in self.SortByFastest() if not x.disabled]
    for (index, other_ns) in enumerate(ns_by_fastest):
      test_servers = []
      for ns in ns_by_fastest:
        if ns.is_slower_replica or ns.disabled:
          continue
        elif ns.ip == other_ns.ip or ns in other_ns.shared_with:
          continue
        # We do extra work here because we do not check for (other, ns), but
        # I believe it is worth the extra time to check it anyways.
        elif (ns.ip, other_ns.ip) in tested:
          continue
        test_servers.append(ns)
        tested.append((ns.ip, other_ns.ip))

      self.msg('Checking nameservers for slow replicas', count=index+1,
               total=len(ns_by_fastest))
      if not other_ns.disabled:
        self.RunCacheCollusionThreads(other_ns, test_servers)

  def RunWildcardStoreThreads(self):
    """Store a wildcard cache value for all nameservers (using threads)."""
    threads = []
    for (index, chunk) in enumerate(util.SplitSequence(self, self.thread_count)):
      self.msg('Launching wildcard check threads', count=index+1, total=self.thread_count)
      thread = TestNameServersThread(chunk, store_wildcard=True)
      thread.start()
      threads.append(thread)

    for (index, thread) in enumerate(threads):
      self.msg('Waiting for wildcard check threads', index+1, len(threads))
      thread.join()

  def RunCacheCollusionThreads(self, other_ns, test_servers):
    """Schedule and manage threading for cache collusion checks."""

    # TODO(tstromberg): Investigate issues with long initial
    # health-check runs.
    threads = []
    thread_count = self.thread_count
    for chunk in util.SplitSequence(test_servers, thread_count):
      thread = TestNameServersThread(chunk, compare_cache=other_ns)
      thread.start()
      threads.append(thread)

    results = []
    for thread in threads:
      thread.join()
      results.extend(thread.results)

    # TODO(tstromberg): Comparing fast/slow at this point is stupid. Move it
    # till after these checks have completed.
    for (shared, slower, faster) in results:
      if shared:
        dur_delta = abs(slower.check_duration - faster.check_duration)
        # Do not disable our current primary DNS server
        if slower.system_position == 0:
          faster.disabled = 'Shares-cache with current primary DNS server'
          slower.warnings.append('shares cache with faster %s' % faster.ip)
        elif slower.is_primary and not faster.is_primary:
          faster.disabled = 'Shares cache wth %s [%s]' % (slower.name, slower.ip)
          slower.warnings.append('shares cache with %s' % faster.ip)
        else:
          slower.disabled = 'Slower replica of %s [%s]' % (faster.name, faster.ip)
          faster.warnings.append('shares cache with %s' % slower.ip)
        slower.shared_with.append(faster)
        faster.shared_with.append(slower)

  def RunHealthCheckThreads(self):
    """Check the health of all of the nameservers (using threads)."""
    threads = []
    servers = list(self)
    random.shuffle(servers)
    for (index, chunk) in enumerate(util.SplitSequence(servers, self.thread_count)):
      self.msg('Launching health check threads', count=index+1, total=self.thread_count)
      thread = TestNameServersThread(chunk)
      thread.start()
      threads.append(thread)

    for (index, thread) in enumerate(threads):
      self.msg('Waiting for health check threads', index+1, len(threads))
      thread.join()

    healthy = [x for x in self if not x.disabled]
    self.msg('%s of %s name servers are healthy' % (len(healthy), len(self)))
