import time
import threading
import dns.resolver
import nameserver
import operator
import random
import util

WILDCARD_DOMAIN = 'blogspot.com.'
EXTRA_NS_SLACK = 3

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
               include_internal=False, threads=1, timeout=2):
    self.seen_ips = set()
    self.seen_names = set()
    self.thread_count = threads
    self.timeout = timeout
              
    super(NameServers, self).__init__()
    for (ip, name) in nameservers:
      self.AddServer(ip, name)

    for (ip, name) in secondary:
      self.AddServer(ip, name, secondary=True)
      
    if include_internal:
      for ip in self.InternalNameServers():
        self.AddServer(ip, 'SYS-%s' % ip, internal=True)


  def AddServer(self, ip, name, secondary=False, internal=False):
    if ip in self.seen_ips:
      return None

    # Add an identifier to the name if necessary.
    if name in self.seen_names:
      for identifier in range(2,10):
        new_name = ''.join((name, '-', str(identifier)))
        if new_name not in self.seen_names:
          name = new_name
          break
        
    ns = nameserver.NameServer(ip, name=name, secondary=secondary)
    self.seen_ips.add(ip)
    self.seen_names.add(name)
    self.append(ns)
    
  def FilterBadorSlowServers(self, count=10):
    
    # TODO(tstromberg): Put caching back for this step.
    self.CheckHealth()
    first_run = []

    for ns in self.SortByFastest():
      if ns.is_healthy:
        if not ns.is_secondary:
          first_run.append(ns)
        elif len(first_run) < (count+EXTRA_NS_SLACK):
          first_run.append(ns)
        else:
          self.remove(ns)
      else:
        self.remove(ns)
        
    self.CheckCacheCollusion()
    best = [ x for x in self.SortByFastest() if not x.is_slower_replica ][0:count]
    # Re-cast as a list() to avoid removing elements while iterating over them.
    for ns in list(self):
      if ns not in best:
        self.remove(ns)

  def InternalNameServers(self):
    """Return list of DNS server IP's used by the host."""
    return dns.resolver.Resolver().nameservers

  def SortByFastest(self):
    return sorted(self, key=operator.attrgetter('check_duration'))

  def CheckCacheCollusion(self):
    """Mark if any nameservers share cache, especially if they are slower."""
        
    for ns in self:
      cache_id = 'www%s.%s' % (random.random(), WILDCARD_DOMAIN)
      response = ns.TimedRequest('A', cache_id)[0]
      ns.cache_check = (cache_id, response)

    # Give the TTL a chance to decrement
    time.sleep(3)
    tested = []

    for other_ns in self.SortByFastest():
      (cache_id, other_response) = other_ns.cache_check
      for ns in self:
        if ns.ip == other_ns.ip:
          continue

        if ns in other_ns.shared_with:
          continue

        # TODO(tstromberg): Make this testable.
        if (ns.ip, other_ns.ip) in tested or (other_ns.ip, ns.ip) in tested:
          continue

        tested.append((ns.ip, other_ns.ip))
        response = ns.TimedRequest('A', cache_id)[0]
        if not response or not response.answer:
          continue

        if not other_response or not other_response.answer:
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
