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

"""Module for all nameserver related activity. Health checks. requests."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import datetime
import time
import random

import sys
import third_party
import dns.exception
import dns.query
import dns.message
import dns.name
import dns.rdataclass
import dns.rdatatype

import util

# Pick the most accurate timer for a platform. Stolen from timeit.py:
if sys.platform == "win32":
  DEFAULT_TIMER = time.clock
else:
  DEFAULT_TIMER = time.time

GOOGLE_CLASS_B = ('74.125',)
WWW_GOOGLE_RESPONSE = ('CNAME www.l.google.com',)
WWW_PAYPAL_RESPONSE = ('66.211.169.', '64.4.241.')
WWW_TPB_RESPONSE = ('194.71.107.',)
OPENDNS_NS = '208.67.220.220'
WILDCARD_DOMAINS = ('live.com.', 'blogspot.com.', 'wordpress.com.')
MIN_SHARING_DELTA_MS = 2
MAX_SHARING_DELTA_MS = 240

# How many checks to consider when calculating ns check_duration
SHARED_CACHE_TIMEOUT_MULTIPLIER = 2.25
CHECK_DURATION_MAX_COUNT = 9

class NameServer(object):
  """Hold information about a particular nameserver."""

  def __init__(self, ip, name=None, internal=False, primary=False):
    self.name = name
    self.ip = ip
    self.is_internal = internal
    self.is_primary = primary
    self.timeout = 60
    self.health_timeout = 30

    self.warnings = []
    self.shared_with = []
    self.is_healthy = True
    self.checks = []
    self.share_check_count = 0
    self.cache_check = None
    self.is_slower_replica = False

  @property
  def check_duration(self):
    return sum([x[3] for x in self.checks[0:CHECK_DURATION_MAX_COUNT]])

  @property
  def failure(self):
    failures = [x for x in self.checks if x[1]]
    if failures:
      return failures[0]
    else:
      return None

  @property
  def warnings_string(self):
    return ', '.join(self.warnings)

  @property
  def warnings_comment(self):
    if self.warnings:
      return '# ' + self.warnings_string
    else:
      return ''

  def __str__(self):
    return '%s [%s]' % (self.name, self.ip)

  def __repr__(self):
    return self.__str__()

  def CreateRequest(self, record, request_type, return_type):
    """Work around a bug in dns/entropy.py that causes IndexErrors."""
    tries = 0
    success = False
    while not success and tries < 10:
      tries += 1
      try:
        request = dns.message.make_query(record, request_type, return_type)
        success = True
      except IndexError, exc:
        print 'Waiting for entropy (%s, tries=%s)' % (exc, tries)
        time.sleep(0.5)
        success = False
    return request

  def Query(self, request, timeout):
    return dns.query.udp(request, self.ip, timeout, 53)

  def TimedRequest(self, type_string, record_string, timeout=None,
                   timer=DEFAULT_TIMER):
    """Make a DNS request, returning the reply and duration it took.

    Args:
      type_string: DNS record type to query (string)
      record_string: DNS record name to query (string)
      timeout: optional timeout (float)

    Returns:
      A tuple of (response, duration in ms [float], exception)

    In the case of a DNS response timeout, the response object will be None.
    """
    request_type = dns.rdatatype.from_text(type_string)
    record = dns.name.from_text(record_string, None)
    request = self.CreateRequest(record, request_type, dns.rdataclass.IN)

    if not timeout:
      timeout = self.timeout

    exc = None
    duration = None
    try:
      start_time = timer()
      response = self.Query(request, timeout)
      duration = timer() - start_time
    except (dns.exception.Timeout), exc:
      response = None
      duration = timer() - start_time
    except (dns.query.BadResponse, dns.message.TrailingJunk,
            dns.query.UnexpectedSource), exc:
      response = None
      duration = timer() - start_time

    return (response, util.SecondsToMilliseconds(duration), exc)

  def TestAnswers(self, record_type, record, expected):
    """Test to see that an answer returns correct IP's.

    Args:
      record_type: text record type for NS query (A, CNAME, etc)
      record: string to query for
      expected: tuple of strings expected in all answers

    Returns:
      (is_broken, warning, duration)
    """
    is_broken = False
    warning = None
    (response, duration, exc) = self.TimedRequest(record_type, record,
                                                  timeout=self.health_timeout)
    failures = []
    if not response:
      is_broken = True
      warning = exc.__class__
    elif not response.answer:
      is_broken = True
      warning = 'No answer'
    else:
      for a in response.answer:
        failed = True
        for string in expected:
          if string in str(a):
            failed=False
            break
        if failed:
          failures.append(a)
    if failures:
      answers = [' + '.join(map(str, x.items)) for x in response.answer]
      answer_text = ' -> '.join(answers)
      warning = '%s hijacked (%s)' % (record, answer_text)
    return (is_broken, warning, duration)

  def ResponseToAscii(self, response):
    if not response:
      return None
    if response.answer:
      answers = [' + '.join(map(str, x.items)) for x in response.answer]
      return ' -> '.join(answers)
    else:
      return 'no answer'

  def TestGoogleComResponse(self):
    return self.TestAnswers('A', 'google.com.', GOOGLE_CLASS_B)

  def TestWwwGoogleComResponse(self):
    return self.TestAnswers('CNAME', 'www.google.com.', WWW_GOOGLE_RESPONSE)

  def TestWwwPaypalComResponse(self):
    return self.TestAnswers('A', 'www.paypal.com.', WWW_PAYPAL_RESPONSE)

  def TestWwwTpbOrgResponse(self):
    return self.TestAnswers('A', 'www.thepiratebay.org.', WWW_TPB_RESPONSE)

  def TestNegativeResponse(self):
    """Test for NXDOMAIN hijaaking."""
    is_broken = False
    warning = None
    poison_test = 'nb.%s.google.com.' % random.random()
    (response, duration, exc) = self.TimedRequest('A', poison_test,
                                                  timeout=self.health_timeout)
    if not response:
      is_broken = True
      warning = str(exc.__class__.__name__)
    elif response.answer:
      warning = 'NXDOMAIN Hijacking'
    return (is_broken, warning, duration)

  def QueryWildcardCache(self, hostname=None, save=True, timeout=None):
    """Make a cache to a random wildcard DNS host, storing the record."""
    if not timeout:
      timeout = self.health_timeout
    is_broken = False
    warning = None
    if not hostname:
      domain = random.choice(WILDCARD_DOMAINS)
      hostname = 'namebench%s.%s' % (random.randint(1,2**32), domain)
    (response, duration, exc) = self.TimedRequest('A', hostname,
                                                  timeout=timeout)
    ttl = None
    if not response:
      is_broken = True
      warning = exc.__class__.__name__
    elif not response.answer:
      is_broken = True
      warning = 'No response'
    else:
      ttl = response.answer[0].ttl

    if save:
      self.cache_check = (hostname, ttl)

    return (response, is_broken, warning, duration)

  def TestWildcardCaching(self):
    return self.QueryWildcardCache(save=True)[1:]

  def TestSharedCache(self, other_ns):
    """Is this nameserver sharing a cache with another nameserver?

    Args:
      other_ns: A nameserver to compare it to.

    Returns:
      A tuple containing:
        - Boolean of whether or not this host has a shared cache
        - The faster NameServer object
        - The slower NameServer object
    """
    if other_ns.cache_check:
      (cache_id, other_ttl) = other_ns.cache_check
    else:
      print "* cache check for %s is missing (skipping)" % other_ns
      return (False, None, None)

    # These queries tend to run slow, and we've already narrowed down the worst.
    timeout = self.health_timeout * SHARED_CACHE_TIMEOUT_MULTIPLIER
    (response, is_broken, warning, duration) = self.QueryWildcardCache(
        cache_id,
        save=False,
        timeout=timeout
    )
    # Try again, but only once. Do penalize them for the first fail however.
    if is_broken:
      sys.stdout.write('_')
      (response, is_broken, warning, duration2) = self.QueryWildcardCache(
          cache_id,
          save=False,
          timeout=timeout
      )
      if is_broken:
        sys.stdout.write('o')
    self.checks.append((cache_id, is_broken, warning, duration))

    if is_broken:
      self.is_healthy = False
    else:
      delta = abs(other_ttl - response.answer[0].ttl)
      if delta > 0:
        if other_ns.check_duration > self.check_duration:
          slower = other_ns
          faster = self
        else:
          slower = self
          faster = other_ns

        if delta > MIN_SHARING_DELTA_MS and delta < MAX_SHARING_DELTA_MS:
          return (True, slower, faster)

    return (False, None, None)

  def CheckHealth(self):
    """Qualify a nameserver to see if it is any good."""
    tests = [self.TestWwwGoogleComResponse,
             self.TestGoogleComResponse,
             self.TestNegativeResponse,
             self.TestWildcardCaching,
             self.TestWwwPaypalComResponse]
    self.checks = []
    self.warnings = []

    for test in tests:
      (is_broken, warning, duration) = test()
      self.checks.append((test.__name__, is_broken, warning, duration))
      if warning:
        self.warnings.append(warning)
      if is_broken:
        self.is_healthy = False
        break
    return self.is_healthy

