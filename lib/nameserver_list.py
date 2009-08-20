# Copyright 2009 Google Inc. All Rights Reserved.

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

NS_CACHE_SLACK = 1.25


class TestNameServersThread(threading.Thread):
  """Quickly test the health of many nameservers with multiple threads."""

  def __init__(self, nameservers):
    threading.Thread.__init__(self)
    self.nameservers = nameservers
    self.results = []

  def run(self):
    for ns in self.nameservers:
      self.results.append(ns.CheckHealth())


class NameServers(list):

  def __init__(self, nameservers, secondary=None, include_internal=False,
               threads=1, cache_dir=None):
    self.seen_ips = set()
    self.seen_names = set()
    self.thread_count = threads
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

  def AddServer(self, ip, name, primary=False, internal=False):

    ns = nameserver.NameServer(ip, name=name, primary=primary,
                               internal=internal)
    self.append(ns)

  def append(self, ns):
    if ns.ip in self.seen_ips:
      print 'I have already seen %s' % ns.ip
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

  def FilterUnwantedServers(self, count=10):
    """Filter out unhealthy or slow replica servers."""
    cached = False
    if self.cache_dir:
      cpath = self._CachePath()
      cached = self._CheckServerCache(cpath)
      if cached:
        self.CheckHealth()

    if not cached:
      print '- Checking health of %s nameservers (%s threads)' % (len(self),
                                                                  self.thread_count)
      self._FilterUnhealthyServers(count * NS_CACHE_SLACK)
      print '- Saving health status of %s best servers to cache' % len(self)
      self._UpdateServerCache(cpath)

    print '- Checking for slow replicas among %s nameservers' % len(self)
    self._FilterSlowerReplicas(count)

  def _CachePath(self):
    """Find a usable and unique location to store health results."""
    checksum = hash(str(sorted([ns.ip for ns in self])))
    return '%s/namebench_cache.%s' % (self.cache_dir, checksum)

  def _CheckServerCache(self, cpath):
    """Check if our health cache has any good data."""
    if os.path.exists(cpath):
      print '- Loading health cache from %s' % cpath
      cf = open(cpath, 'r')
      try:
        data = pickle.load(cf)
        print '- %s nameservers found in cache' % len(data)
        self._Reset(data)
        return True
      except EOFError:
        pass

    print '- No server health cache found in %s' % cpath
    return False

  def _Reset(self, keepers):
    """Reset the list and append the keepers (rename method)."""
    self.seen_ips = set()
    self.seen_names = set()
    super(NameServers, self).__init__()
    for ns in keepers:
      self.append(ns)

  def _UpdateServerCache(self, cpath):
    """Update the cache with our object."""
    cf = open(cpath, 'w')
    try:
      pickle.dump(self, cf)
    except TypeError, exc:
      print "* Could not save cache: %s" % exc

  def _FilterUnhealthyServers(self, count):
    """Only keep the best count servers."""
    self.CheckHealth()
    keep = [x for x in self if x.is_primary and x.is_healthy]
    for ns in self.SortByFastest():
      if not ns.is_primary and len(keep) < count:
        keep.append(ns)
    self._Reset(keep)

  def _FilterSlowerReplicas(self, count):
    self.CheckCacheCollusion()
    usable = [x for x in self.SortByFastest() if not x.is_slower_replica]
    keep = [x for x in usable if x.is_primary]
    shortfall = count - len(keep)
    if shortfall > 0:
      for ns in [x for x in usable if not x.is_primary][0:shortfall]:
        keep.append(ns)
    self._Reset(keep)

  def InternalNameServers(self):
    """Return list of DNS server IP's used by the host."""
    return dns.resolver.Resolver().nameservers

  def SortByFastest(self):
    """Return a list of healthy servers in fastest-first order."""
    fastest = sorted(self, key=operator.attrgetter('check_duration'))
    return [x for x in fastest if x.is_healthy]

  def CheckCacheCollusion(self):
    """Mark if any nameservers share cache, especially if they are slower."""

    # Give the TTL a chance to decrement
    time.sleep(3)
    tested = []

    for other_ns in self.SortByFastest():
      for ns in self.SortByFastest():
        if (ns.ip, other_ns.ip) in tested or (other_ns.ip, ns.ip) in tested:
          continue

        if ns.ip == other_ns.ip or ns in other_ns.shared_with:
          continue

        (is_shared, slower_ns) = self.AreServersSharingCache(ns, other_ns)
        tested.append((ns.ip, other_ns.ip))

        if is_shared:
          ns.warnings.append('shares cache with %s' % other_ns.ip)
          other_ns.warnings.append('shares cache with %s' % ns.ip)
          other_ns.shared_with.append(ns)
          ns.shared_with.append(other_ns)
          slower_ns.is_slower_replica = True

  def AreServersSharingCache(self, ns_a, ns_b):
    """Are two servers sharing cache?

    Args:
      ns_a: first nameserver
      ns_b: second nameserver

    Returns:
      is_shared (boolean)
      slower_nameserver
    """

    (cache_id, response_a) = ns_a.cache_check
    (response_b, is_broken) = ns_b.QueryWildcardCache(cache_id)[0:2]

    if is_broken:
      ns_b.is_healthy = False
    else:
      delta = abs(response_a.answer[0].ttl - response_b.answer[0].ttl)
      if delta > 0:
        dur_delta = abs(ns_a.check_duration - ns_b.check_duration)

        if ns_a.check_duration > ns_b.check_duration:
          slower = ns_a
          faster = ns_b
        else:
          slower = ns_b
          faster = ns_a

        if delta > 1 and delta < 240:
          print ('  * %s shares cache with %s (delta=%s, %sms slower)' %
               (slower, faster, delta, dur_delta))
          return (True, slower)

    return (False, None)

  def CheckHealth(self):
    """Check the health of all of the nameservers (using threads)."""
    threads = []
    for chunk in util.split_seq(self, self.thread_count):
      thread = TestNameServersThread(chunk)
      thread.start()
      threads.append(thread)

    results = []
    for thread in threads:
      thread.join()
      results.extend(thread.results)

    return results
