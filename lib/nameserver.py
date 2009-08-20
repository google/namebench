# Copyright 2009 Google Inc. All Rights Reserved.

"""Module for all nameserver related activity. Health checks. requests."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import datetime
import operator
import random
import time
import util

import dns.name
import dns.rdataclass
import dns.rdatatype
import dns.resolver
import dns.reversename

DEFAULT_TIMEOUT = 4
HEALTH_TIMEOUT = 2
GOOGLE_CLASS_B = '74.125'
WILDCARD_DOMAIN = 'laterooms.com.'
WWW_GOOGLE_RESPONSE = 'CNAME www.l.google.com'
OPENDNS_NS = '208.67.220.220'


class NameServer(object):
  """Hold information about a particular nameserver."""


  def __init__(self, ip, name=None, internal=False, primary=False):
    self.name = name
    self.ip = ip
    self.is_internal = internal
    self.is_primary = primary

    self.warnings = []
    self.results = []
    self.shared_with = []
    self.is_healthy = True
    self.checks = []
    self.cache_check = None
    self.is_slower_replica = False


  def _get_check_duration(self):
    return sum([ x[3] for x in self.checks])

  check_duration = property(_get_check_duration, None)

  def __str__(self):
    return '%s [%s]' % (self.name, self.ip)

  def __repr__(self):
    return self.__str__()

  def Query(self, request, timeout):
    return dns.query.udp(request, self.ip, timeout, 53)

  def TimedRequest(self, type_string, record_string, timeout=DEFAULT_TIMEOUT):
    """Make a DNS request, returning the reply and duration it took.

    Args:
      nameserver: IP of DNS server to query (string)
      type_string: DNS record type to query (string)
      record_string: DNS record name to query (string)

    Returns:
      A tuple of (response, duration [float], exception)

    In the case of a DNS response timeout, the response object will be None.
    """
    request_type = dns.rdatatype.from_text(type_string)
    record = dns.name.from_text(record_string, None)
    return_type = dns.rdataclass.IN
    request = dns.message.make_query(record, request_type, return_type)

    start_time = datetime.datetime.now()
    exc = None
    try:
      response = self.Query(request, timeout)
    except (dns.exception.Timeout), exc:
      response = None
    except (dns.query.BadResponse, dns.message.TrailingJunk, dns.query.UnexpectedSource), exc:
      response = None
    duration = util.TimeDeltaToMilliseconds(datetime.datetime.now() - start_time)
    return (response, duration, exc)

  def TestAnswers(self, record_type, record, expected):
    """Test to see that an answer returns correct IP's.

    Returns:
      (is_broken, warning, duration)
    """
    is_broken = False
    warning = None
    (response, duration, exc) = self.TimedRequest(record_type, record, timeout=HEALTH_TIMEOUT)
    if not response:
      is_broken = True
      warning = exc.__class__
    elif not response.answer:
      is_broken = True
      result = False
      warning = 'No answer'
    else:
      for a in response.answer:
        if expected not in str(a):
#          warning = '%s may be hijacked (%s)' % (record, str(a))
          warning = '%s may be hijacked' % record
    return (is_broken, warning, duration)

  def TestGoogleComResponse(self):
    return self.TestAnswers('A', 'google.com.', GOOGLE_CLASS_B)

  def TestWwwGoogleComResponse(self):
    return self.TestAnswers('CNAME', 'www.google.com.', WWW_GOOGLE_RESPONSE)

  def TestNegativeResponse(self):
    is_broken = False
    warning = None
    poison_test = 'nb.%s.google.com.' % random.random()
    (response, duration, exc) = self.TimedRequest('A', poison_test, timeout=HEALTH_TIMEOUT)
    if not response:
      is_broken = True
      warning = exc.__class__
    elif response.answer:
      warning = 'NXDOMAIN Hijacking'
    return (is_broken, warning, duration)
  
  def QueryWildcardCache(self, hostname=None):
    is_broken = False
    warning = None
    if not hostname:
      hostname = 'www%s.%s' % (random.random(), WILDCARD_DOMAIN)
        
    (response, duration, exc) = self.TimedRequest('A', hostname, timeout=HEALTH_TIMEOUT)
    if not response:
      is_broken = True
      warning = exc.__class__
    elif not response.answer:
      is_broken = True
      warning = 'No response'

    if not self.cache_check:
      self.cache_check = (hostname, response)
    
    return (response, is_broken, warning, duration)
  
  def TestWildcardCaching(self, hostname=None):
    (response, is_broken, warning, duration) = self.QueryWildcardCache()
    return (is_broken, warning, duration)

  def CheckHealth(self):
    """Qualify a nameserver to see if it is any good."""
    tests = [self.TestWwwGoogleComResponse,
             self.TestGoogleComResponse,
             self.TestNegativeResponse,
             self.TestWildcardCaching]
    self.checks = []
    self.warnings = []

    for test in tests:
      (is_broken, warning, duration) = test()
      if is_broken:
        self.is_healthy = False
        if self.is_primary:
          print '  * %s is unhealthy: %s %s' % (self, test.__name__, warning)
        break

      if warning:
        self.warnings.append(warning)
      self.checks.append((test.__name__, is_broken, warning, duration))

    if self.warnings:
      print '  o %s: %s' % (self.name, ', '.join(self.warnings))

    return self.is_healthy

