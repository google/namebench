# Copyright 2009 Google Inc. All Rights Reserved.

"""Module for all nameserver related activity. Health checks. requests."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import datetime
import operator
import random
import threading
import time

import dns.name
import dns.rdataclass
import dns.rdatatype
import dns.resolver
import dns.reversename

DEFAULT_TIMEOUT = 10
GOOGLE_CLASS_B = '74.125'
WILDCARD_DOMAIN = 'laterooms.com.'
WWW_GOOGLE_RESPONSE = 'CNAME www.l.google.com'
WWW_YAHOO_RESPONSE = 'CNAME www.wa1.b.yahoo.com'
OPENDNS_NS = '208.67.220.220'


def TimeDeltaToMilliseconds(td):
  """Convert timedelta object to milliseconds."""
  return (td.days*86400000) + (td.seconds*1000) + (td.microseconds/1000.0)


def split_seq(seq, size):
  """Recipe From http://code.activestate.com/recipes/425397/ ."""
  newseq = []
  splitsize = 1.0/size*len(seq)
  for i in range(size):
    newseq.append(seq[int(round(i*splitsize)):int(round((i+1)*splitsize))])
  return newseq


class TestNameServersThread(threading.Thread):
  """Quickly test the health of many nameservers with multiple threads."""

  def __init__(self, timeout, nameservers):
    threading.Thread.__init__(self)
    self.nameservers = nameservers
    self.test = NameServerTests(timeout=timeout)
    self.results = []

  def run(self):
    for (ip, desc) in self.nameservers:
      ns = NameServerData(ip, desc)
      self.results.append(self.test.QualifyNameServer(ns))


class NameServerData(object):
  """Hold information about a particular nameserver."""

  def __init__(self, ip, name):
    self.name = name
    self.ip = ip
    self.notes = []
    self.results = []
    self.cache_check = None
    self.shared_with = []
    self.is_healthy = False
    self.checks = []
    self.check_duration = 0
    self.shares_with_faster = False

  def __str__(self):
    return '%s [%s]' % (self.name, self.ip)


class NSLookup(object):
  """Helper methods for querying DNS servers."""

  def __init__(self, thread_count=1, timeout=DEFAULT_TIMEOUT):
    self.thread_count = thread_count
    self.timeout = timeout

  def InternalNameServers(self):
    """Return list of DNS server IP's used by the host."""
    return dns.resolver.Resolver().nameservers

  def DNSQuery(self, request, nameserver, port=53):
    return dns.query.udp(request, nameserver, self.timeout, port)

  def TimedDNSRequest(self, nameserver, type_string, record_string):
    """Make a DNS request, returning the reply and duration it took.

    Args:
      nameserver: IP of DNS server to query (string)
      type_string: DNS record type to query (string)
      record_string: DNS record name to query (string)

    Returns:
      A tuple of (response, duration [float])

    In the case of a DNS response timeout, the response object will be None.
    """
    request_type = dns.rdatatype.from_text(type_string)
    record = dns.name.from_text(record_string, None)
    return_type = dns.rdataclass.IN
    request = dns.message.make_query(record, request_type, return_type)

    start_time = datetime.datetime.now()
    try:
      response = self.DNSQuery(request, nameserver)
    except dns.exception.Timeout:
      response = None
    except dns.message.TrailingJunk:
      print '%s is returning invalid DNS responses (trailing junk)' % nameserver
      response = None
    duration = TimeDeltaToMilliseconds(datetime.datetime.now() - start_time)
    return (response, duration)


class NameServerTests(NSLookup):
  """Poke and prod sets of nameservers via multiple methods."""

  def TestGoogleComResponse(self, ip):
    """Test to see that A google.com returns correct IP's."""
    result = None
    (response, duration) = self.TimedDNSRequest(ip, 'A', 'google.com.')
    if not response:
      result = 'timeout'
    elif not response.answer:
      result = 'unusable'
    else:
      for a in response.answer:
        if GOOGLE_CLASS_B not in str(a):
          result = 'google.com hijacked' % a
    return (result, duration, response)

  def TestWwwGoogleComResponse(self, ip):
    """Test to see that www.google.com returns correct CNAME."""
    result = None
    (response, duration) = self.TimedDNSRequest(ip, 'CNAME', 'www.google.com.')
    if not response:
      result = 'timeout'
    elif not response.answer:
      result = 'unusable'
    else:
      if WWW_GOOGLE_RESPONSE not in response.answer[0].to_text():
        result = 'www.google.com hijacked'
    return (result, duration, response)

  def TestWwwYahooComResponse(self, ip):
    """Test to see that www.yahoo.com returns correct CNAME."""
    result = None
    (response, duration) = self.TimedDNSRequest(ip, 'CNAME', 'www.yahoo.com.')
    if not response:
      result = 'timeout'
    elif not response.answer:
      result = 'unusable'
    else:
      if WWW_YAHOO_RESPONSE not in response.answer[0].to_text():
        result = 'www.yahoo.com hijacked'
    return (result, duration, response)

  def TestNegativeResponse(self, ip):
    result = None
    poison_test = 'nb.%s.google.com.' % random.random()
    (response, duration) = self.TimedDNSRequest(ip, 'A',
                                                poison_test)
    if not response:
      result = 'timeout'
    elif response.answer:
      result = 'negative response poisoning'
    return (result, duration, response)

  def QualifyNameServer(self, ns):
    """Qualify a nameserver to see if it is any good."""
    tests = [self.TestWwwGoogleComResponse,
             self.TestGoogleComResponse,
             self.TestNegativeResponse]
# No one messes with yahoo.com yet =(
#             self.TestWwwYahooComResponse,

    for test in tests:
      (note, duration, response) = test(ns.ip)
      # Turn this into an attribute!
      if note:
        ns.notes.append(note)
      ns.checks.append((test.__name__, note, duration, response))
      if note in ('timeout', 'unusable'):
        ns.is_healthy = False
        return ns

    ns.is_healthy = True
    if ns.notes:
      print '  * %s: %s' % (ns, ', '.join(ns.notes))

    ns.check_duration = sum([x[2] for x in ns.checks])
    return ns

  def SortByFastest(self, nameservers):
    return sorted(nameservers, key=operator.attrgetter('check_duration'))

  def CheckCacheCollusion(self, nameservers):
    """Mark if any nameservers share cache, especially if they are slower."""
    # TODO(tstromberg): Rework algorithm so that nameserver combinations are
    # tested only once rather than twice.    
    for ns in nameservers:
      cache_id = 'www%s.%s' % (random.random(), WILDCARD_DOMAIN)
      response = self.TimedDNSRequest(ns.ip, 'A', cache_id)[0]
      ns.cache_check = (cache_id, response)

    # Give the TTL a chance to decrement
    time.sleep(3)
    for other_ns in self.SortByFastest(nameservers):
      (cache_id, other_response) = other_ns.cache_check
      for ns in nameservers:
        if ns.ip == other_ns.ip:
          continue

        if ns in other_ns.shared_with:
          continue

        response = self.TimedDNSRequest(ns.ip, 'A', cache_id)[0]
        if not response or not response.answer:
          continue

        if not other_response or not other_response.answer:
          continue

        # Some nameservers play games with TTL's, be specific.
        delta = other_response.answer[0].ttl - response.answer[0].ttl
        if delta > 1 and delta < 60:
          ns.notes.append('shares cache with %s' % other_ns.ip)
          other_ns.notes.append('shares cache with %s' % ns.ip)
          other_ns.shared_with.append(ns)
          ns.shared_with.append(other_ns)
          dur_delta = ns.check_duration - other_ns.check_duration
          if dur_delta > 0:
            ns.shares_with_faster = True
            print ('  * %s shares cache with %s (%sms slower)' %
                   (ns, other_ns, dur_delta))
        elif delta != 0 and abs(delta) < 1500:
          print ('  * %s [%s] has a different TTL than %s [%s], delta=%s' % (ns, response.answer[0].ttl, other_ns,  other_response.answer[0].ttl, delta))
          
    return nameservers

  def FindUsableNameServers(self, nameservers, internal=False):
    """Discover what nameservers are available.

    Args:
      nameservers: A list of tuples in (ip address, name) format
      internal: Include system nameservers (boolean, default=False)

    Returns:
      A list of NameServerData objects with healthy nameservers.
    """
    if internal:
      for (index, ip) in enumerate(self.InternalNameServers()):
        print '  o Including system nameserver #%s: %s' % (index+1, ip)
        nameservers.append((ip, 'SYS%s-%s' % ((index+1), ip)))

    chunks = split_seq(nameservers, self.thread_count)
    threads = []
    for chunk in chunks:
      thread = TestNameServersThread(self.timeout, chunk)
      thread.start()
      threads.append(thread)

    results = []
    for thread in threads:
      thread.join()
      results.extend(thread.results)

    return self.SortByFastest([x for x in results if x.is_healthy])

  def AreDNSPacketsIntercepted(self):
    """Check if our packets are actually getting to the correct servers."""
    # TODO(tstromberg): Add a check for one other nameservice.
    response = self.TimedDNSRequest(OPENDNS_NS, 'TXT',
                                    'which.opendns.com.')[0]
    for answer in response.answer:
      if 'I am not an OpenDNS resolver' in answer.to_text():
        return True
    return False

