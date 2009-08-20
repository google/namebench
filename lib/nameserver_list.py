import time
import os
import threading
import dns.resolver
import nameserver
import operator
import random
import util
import pickle

WILDCARD_DOMAIN = 'blogspot.com.'
NS_CACHE_SLACK = 1.25

class TestNameServersThread(threading.Thread):
  """Quickly test the health of many nameservers with multiple threads."""

  def __init__(self, timeout, nameservers):
    threading.Thread.__init__(self)
    self.nameservers = nameservers
    self.results = []

  def run(self):
    for ns in self.nameservers:
      self.results.append(ns.CheckHealth())

class NameServers(list):

  def __init__(self, nameservers, secondary=[],
               include_internal=False, threads=1, timeout=2,
               cache_dir=None):
    self.seen_ips = set()
    self.seen_names = set()
    self.thread_count = threads
    self.timeout = timeout
    self.cache_dir = cache_dir

    super(NameServers, self).__init__()
    for (ip, name) in nameservers:
      self.AddServer(ip, name, primary=True)

    for (ip, name) in secondary:
      self.AddServer(ip, name, primary=False)

    if include_internal:
      for ip in self.InternalNameServers():
        self.AddServer(ip, 'SYS-%s' % ip, internal=True, primary=True)

  def AddServer(self, ip, name, primary=False, internal=False):
    ns = nameserver.NameServer(ip, name=name, primary=primary)
    self.append(ns)

  def append(self, ns):
    if ns.ip in self.seen_ips:
      print 'I have already seen %s' % ns.ip
      return None

    # Add an identifier to the name if necessary.
    if ns.name in self.seen_names:
      for identifier in range(2,10):
        new_name = ''.join((ns.name, '-', str(identifier)))
        if new_name not in self.seen_names:
          ns.name = new_name
          break

    super(NameServers, self).append(ns)
    self.seen_ips.add(ns.ip)
    self.seen_names.add(ns.name)


  def FilterUnwantedServers(self, count=10):
    cached = False
    if self.cache_dir:
      cpath = self._CachePath()
      cached = self._CheckServerCache(cpath)
      if cached:
        self.CheckHealth()

    if not cached:
      print '- Checking health of %s nameservers (%s threads)' % (len(self), self.thread_count)
      self._FilterUnhealthyServers(count * NS_CACHE_SLACK)
      print '- Saving health status of %s best servers to cache' % len(self)
      self._UpdateServerCache(cpath)

    print '- Checking for slow replicas among %s nameservers' % len(self)
    self._FilterSlowerReplicas(count)

  def _CachePath(self):
    checksum = hash(str(sorted([ ns.ip for ns in self ])))
    return '%s/namebench_cache.%s' % (self.cache_dir, checksum)

  def _CheckServerCache(self, cpath):
    if os.path.exists(cpath):
      print '- Loading health cache from %s' % cpath
      cf = open(cpath, 'r')
      data = pickle.load(cf)
      print '- %s nameservers found in cache' % len(data)
      self._Reset(data)
      return True
    else:
      print '- No server health cache found in %s' % cpath
      return False

  def _Reset(self, keepers):
    """Reset the list and append the keepers (rename method)"""
    self.seen_ips = set()
    self.seen_names = set()
    super(NameServers, self).__init__()
    for ns in keepers:
      self.append(ns)

  def _UpdateServerCache(self, cpath):
    cf = open(cpath, 'w')
    pickle.dump(self, cf)

  def _FilterUnhealthyServers(self, count):
    self.CheckHealth()
    keep = [ x for x in self if x.is_primary and x.is_healthy ]
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
      for ns in [ x for x in usable if not x.is_primary][0:shortfall]:
        keep.append(ns)

    self._Reset(keep)

  def InternalNameServers(self):
    """Return list of DNS server IP's used by the host."""
    return dns.resolver.Resolver().nameservers

  def SortByFastest(self):
    fastest = sorted(self, key=operator.attrgetter('check_duration'))
    return [ x for x  in fastest if x.is_healthy ]

  def CheckCacheCollusion(self):
    """Mark if any nameservers share cache, especially if they are slower."""

    # Give the TTL a chance to decrement
    time.sleep(3)
    tested = []

    for other_ns in self.SortByFastest():
      (cache_id, other_response) = other_ns.cache_check
      for ns in self.SortByFastest():
        if ns.ip == other_ns.ip:
          continue

        if ns in other_ns.shared_with:
          continue

        # TODO(tstromberg): Make this testable.
        if (ns.ip, other_ns.ip) in tested or (other_ns.ip, ns.ip) in tested:
          continue
        
        (response, is_broken, warning, duration) = ns.QueryWildcardCache(cache_id)
        tested.append((ns.ip, other_ns.ip))
        if is_broken:
          ns.is_healthy = False
          continue

        # Some nameservers play games with TTL's, be specific.
        delta = other_response.answer[0].ttl - response.answer[0].ttl
        if delta > 1 and delta < 120:
          ns.warnings.append('shares cache with %s' % other_ns.ip)
          other_ns.warnings.append('shares cache with %s' % ns.ip)
          other_ns.shared_with.append(ns)
          ns.shared_with.append(other_ns)
          dur_delta = ns.check_duration - other_ns.check_duration
          if dur_delta > 0:
            ns.is_slower_replica = True
            print ('  * %s shares cache with %s (delta=%s, %sms slower)' %
                   (ns, other_ns, delta, dur_delta))
        elif delta != 0 and abs(delta) < 1500:
          print ('  * %s [%s] has a different TTL than %s [%s], delta=%s' % (ns, response.answer[0].ttl, other_ns,  other_response.answer[0].ttl, delta))

  def CheckHealth(self):
    """Discover what nameservers are available.

    Args:
      nameservers: A list of tuples in (ip address, name) format
      internal: Include system nameservers (boolean, default=False)

    Returns:
      A list of NameServerData objects with healthy nameservers.
    """
    threads = []
    for chunk in util.split_seq(self, self.thread_count):
      thread = TestNameServersThread(self.timeout, chunk)
      thread.start()
      threads.append(thread)

    results = []
    for thread in threads:
      thread.join()
      results.extend(thread.results)

    return results
