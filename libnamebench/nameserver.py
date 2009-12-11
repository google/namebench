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
import traceback
import random

import sys

# See if a third_party library exists -- use it if so.
try:
  import third_party
except ImportError:
  pass

# external dependencies (from third_party)
import dns.exception
import dns.query
import dns.message
import dns.name
import dns.rcode
import dns.rdataclass
import dns.rdatatype
import dns.reversename
import dns.resolver

import util

# Pick the most accurate timer for a platform. Stolen from timeit.py:
if sys.platform[:3] == 'win':
  DEFAULT_TIMER = time.clock
else:
  DEFAULT_TIMER = time.time

# Based on observed behaviour - not authorative, and very subject to change.
# TODO(tstromberg): Find the best way to determine hijacking without hardcoding.
GOOGLE_SUBNETS = ('74.125.', '66.102.9.', '66.102.11.', '66.102.13.',
                  '66.102.7.', '66.102.9.', '209.85.1', '209.85.22',
                  '209.85.231', '64.233.16', '64.233.17', '64.233.18',
                  '66.249.8', '66.249.9', '72.14.2', '216.239.59')

WWW_GOOGLE_RESPONSE = ('CNAME www.l.google.com',)
WWW_PAYPAL_RESPONSE = ('66.211.169.', '64.4.241.')
WWW_FACEBOOK_RESPONSE = ('69.63.18')
WINDOWSUPDATE_MICROSOFT_RESPONSE = ('windowsupdate.microsoft.nsatc.net.')
WWW_TPB_RESPONSE = ('194.71.107.',)
OPENDNS_NS = '208.67.220.220'
WILDCARD_DOMAINS = ('live.com.', 'blogspot.com.', 'wordpress.com.')

# How many failures before we disable system nameservers
MAX_SYSTEM_FAILURES = 4
ERROR_PRONE_RATE = 10

# How many checks to consider when calculating ns check_duration
SHARED_CACHE_TIMEOUT_MULTIPLIER = 5
MAX_STORE_ATTEMPTS = 4
TOTAL_WILDCARDS_TO_STORE = 2

class NameServer(object):
  """Hold information about a particular nameserver."""

  def __init__(self, ip, name=None, internal=False, primary=False):
    self.name = name
    self.ip = ip
    self.is_system = internal
    self.system_position = None
    self.is_primary = primary
    self.timeout = 60
    self.health_timeout = 30
    self.warnings = set()
    self.shared_with = set()
    self.disabled = False
    self.checks = []
    self.request_count = 0
    self.error_count = 0
    self.failed_test_count = 0
    self.share_check_count = 0
    self.cache_checks = []
    self.is_slower_replica = False
    self.timer = DEFAULT_TIMER

  @property
  def check_average(self):
    return util.CalculateListAverage([x[3] for x in self.checks])

  @property
  def check_duration(self):
    return sum([x[3] for x in self.checks])

  @property
  def failure(self):
    failures = [x for x in self.checks if x[1]]
    if failures:
      return failures[0]
    else:
      return None

  @property
  def warnings_string(self):
    if self.disabled:
      return '(excluded: %s)' % self.disabled
    else:
      return ', '.join(map(str,self.warnings))

  @property
  def warnings_comment(self):
    if self.warnings or self.disabled:
      return '# ' + self.warnings_string
    else:
      return ''

  @property
  def hostname(self):
    try:
      answer = dns.resolver.query(dns.reversename.from_address(self.ip), 'PTR')
      if answer:
        return str(answer[0])
    except:
      return ''

  @property
  def is_error_prone(self):
    if self.error_rate >= ERROR_PRONE_RATE:
      return True
    else:
      return False
      
  @property
  def error_rate(self):
    if not self.error_count or not self.request_count:
      return 0
    else:
      return (float(self.error_count) / float(self.request_count)) * 100

  def __str__(self):
    return '%s [%s]' % (self.name, self.ip)

  def __repr__(self):
    return self.__str__()
    
  def AddFailure(self, message):
    """Add a failure for this nameserver. This will effectively disable it's use."""
    self.failed_test_count += 1
    if self.is_system:
      print "* System DNS fail #%s/%s: %s %s" % (self.failed_test_count, MAX_SYSTEM_FAILURES, self, message)      
      if self.failed_test_count >= MAX_SYSTEM_FAILURES:
        print "* Disabling %s - %s failures" % (self, self.failed_test_count)
        self.disabled = message
    else:
      self.disabled = message
      

  def CreateRequest(self, record, request_type, return_type):
    """Function to work around any dnspython make_query quirks."""
    return dns.message.make_query(record, request_type, return_type)

  def Query(self, request, timeout):
    return dns.query.udp(request, self.ip, timeout, 53)

  def TimedRequest(self, type_string, record_string, timeout=None):
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
    request = None
    self.request_count += 1
    
    # Sometimes it takes great effort just to craft a UDP packet.
    try:
      request = self.CreateRequest(record, request_type, dns.rdataclass.IN)
    except ValueError, exc:
      if not request:
        return (None, 0, exc)

    if not timeout:
      timeout = self.timeout

    exc = None
    duration = None
    try:
      start_time = self.timer()
      response = self.Query(request, timeout)
      duration = self.timer() - start_time
    except (dns.exception.Timeout), exc:
      response = None
    except (dns.query.BadResponse, dns.message.TrailingJunk,
            dns.query.UnexpectedSource), exc:
      response = None
    except (KeyboardInterrupt, SystemExit, SystemError), exc:
      raise exc
    except:
      (exc, error) = sys.exc_info()[0:2]
      print "* Error with %s: %s (%s)" % (self, exc, error)
      response = None

    if not response:
      self.error_count += 1

    if not duration:
      duration = self.timer() - start_time

    return (response, util.SecondsToMilliseconds(duration), exc)

  def TestAnswers(self, record_type, record, expected, fatal=True):
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
      if fatal:
        is_broken = True
      # Avoid preferring broken DNS servers that respond quickly
      duration = self.health_timeout
      warning = 'No answer for %s' % record
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
      return dns.rcode.to_text(response.rcode())


  def TestGoogleComResponse(self):
    return self.TestAnswers('A', 'google.com.', GOOGLE_SUBNETS)

  def TestWwwGoogleComResponse(self):
    return self.TestAnswers('CNAME', 'www.google.com.', WWW_GOOGLE_RESPONSE)

  def TestWwwPaypalComResponse(self):
    return self.TestAnswers('A', 'www.paypal.com.', WWW_PAYPAL_RESPONSE)

  def TestWwwTpbOrgResponse(self):
    return self.TestAnswers('A', 'www.thepiratebay.org.', WWW_TPB_RESPONSE,
                            fatal=False)

  def TestWwwFacebookComResponse(self):
    return self.TestAnswers('A', 'www.facebook.com.', WWW_FACEBOOK_RESPONSE)

  def TestWindowsUpdateMicrosoftResponse(self):
    return self.TestAnswers('A', 'windowsupdate.microsoft.com.', WINDOWSUPDATE_MICROSOFT_RESPONSE)


  def TestLocalhostResponse(self):
    (response, duration, exc) = self.TimedRequest('A', 'localhost.',
                                                  timeout=self.health_timeout)
    if exc:
      is_broken = True
      warning = str(exc.__class__.__name__)
    else:
      is_broken = False
      warning = None
    return (is_broken, warning, duration)


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


  def StoreWildcardCache(self):
    """Store a set of wildcard records."""
    timeout = self.health_timeout * SHARED_CACHE_TIMEOUT_MULTIPLIER
    attempted = []

    while len(self.cache_checks) != TOTAL_WILDCARDS_TO_STORE:
      if len(attempted) == MAX_STORE_ATTEMPTS:
        self.AddFailure('Could not recursively query: %s' % ', '.join(attempted))
        return False
      domain = random.choice(WILDCARD_DOMAINS)
      hostname = 'namebench%s.%s' % (random.randint(1,2**32), domain)
      attempted.append(hostname)
      (response, duration, exc) = self.TimedRequest('A', hostname, timeout=timeout)
      if response and response.answer:
        self.cache_checks.append((hostname, response, self.timer()))
      else:
        sys.stdout.write('x')


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
    timeout = self.health_timeout * SHARED_CACHE_TIMEOUT_MULTIPLIER
    checked = []
    shared = False

    if self.disabled or other_ns.disabled:
      return False

    if not other_ns.cache_checks:
      print "%s has no cache checks" % other_ns
      return False

    for (ref_hostname, ref_response, ref_timestamp) in other_ns.cache_checks:
      (response, duration, exc) = self.TimedRequest('A', ref_hostname, timeout=timeout)
      
      if response and response.answer:
        ref_ttl = ref_response.answer[0].ttl
        ttl = response.answer[0].ttl
        delta = abs(ref_ttl - ttl)
        query_age = self.timer() - ref_timestamp
        delta_age_delta = abs(query_age - delta)
        
        if delta > 0 and delta_age_delta < 2:
          return other_ns
      else:
        sys.stdout.write('x')

      if not checked:
        self.checks.append(('cache', exc, exc, duration))
      checked.append(ref_hostname)
      
    if not checked:
      self.AddFailure('Failed to test %s wildcard caches'  % len(other_ns.cache_checks))    
    return shared

  def CheckHealth(self, fast_check=False):
    """Qualify a nameserver to see if it is any good."""
    
    if fast_check:
      tests = [self.TestLocalhostResponse]
    else:
      tests = [self.TestWwwGoogleComResponse,
               self.TestGoogleComResponse,
               self.TestNegativeResponse,
               self.TestWwwFacebookComResponse,
               self.TestWindowsUpdateMicrosoftResponse,
               self.TestWwwPaypalComResponse,
               self.TestWwwTpbOrgResponse]

    for test in tests:
      (is_broken, warning, duration) = test()
      self.checks.append((test.__name__, is_broken, warning, duration))
      if warning:
        self.warnings.add(warning)
      if is_broken:
        self.AddFailure('Failed %s: %s' % (test.__name__, warning))
      if self.disabled:
        break

    return self.disabled

