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
if sys.platform == "win32":
  DEFAULT_TIMER = time.clock
else:
  DEFAULT_TIMER = time.time

GOOGLE_CLASS_B = ('74.125',)
WWW_GOOGLE_RESPONSE = ('CNAME www.l.google.com',)
WWW_PAYPAL_RESPONSE = ('66.211.169.', '64.4.241.')
WWW_FACEBOOK_RESPONSE = ('69.63.18')
WINDOWSUPDATE_MICROSOFT_RESPONSE = ('windowsupdate.microsoft.nsatc.net.')
WWW_TPB_RESPONSE = ('194.71.107.',)
OPENDNS_NS = '208.67.220.220'
WILDCARD_DOMAINS = ('live.com.', 'blogspot.com.', 'wordpress.com.')
MIN_SHARING_DELTA_MS = 3
MAX_SHARING_DELTA_MS = 90
TOTAL_WILDCARDS_TO_STORE = 2

# How many checks to consider when calculating ns check_duration
SHARED_CACHE_TIMEOUT_MULTIPLIER = 4
MAX_STORE_ATTEMPTS = 4

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
    self.share_check_count = 0
    self.cache_checks = []
    self.is_slower_replica = False
    self.timer = DEFAULT_TIMER

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
      return ', '.join(self.warnings)

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

  def __str__(self):
    return '%s [%s]' % (self.name, self.ip)

  def __repr__(self):
    return self.__str__()

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
    return self.TestAnswers('A', 'google.com.', GOOGLE_CLASS_B)

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
    
    attempts = 0

    while len(self.cache_checks) != TOTAL_WILDCARDS_TO_STORE:
      attempts += 1
      if attempts == MAX_STORE_ATTEMPTS:
#        print "%s is unable to query wildcard caches" % self
        self.disabled = 'Unable to recursively query wildcard hostnames'
        return False
      domain = random.choice(WILDCARD_DOMAINS)
      hostname = 'namebench%s.%s' % (random.randint(1,2**32), domain)
      (response, duration, exc) = self.TimedRequest('A', hostname, timeout=timeout)
      if response and response.answer:
#        print "%s storing %s TTL=%s (at %s)"  % (self, hostname, response.answer[0].ttl, self.timer())
        self.cache_checks.append((hostname, response, self.timer()))


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
      ref_ttl = ref_response.answer[0].ttl
      if not response or not response.answer:
#        print "%s failed to get answer for %s in %sms [%s]" % (self, ref_hostname, duration, exc)
        continue
      
      checked.append(ref_hostname)
      ttl = response.answer[0].ttl
      delta = abs(ref_ttl - ttl)
      query_age = self.timer() - ref_timestamp
      delta_age_delta = abs(query_age - delta)
      
#      print "%s check against %s for %s: delta=%s age=%s" % (self, other_ns, ref_hostname, delta, query_age)
      if delta > 0 and delta_age_delta < 2:
        print "- %s shared with %s on %s (delta=%s, age_delta=%s)" % (self, other_ns, ref_hostname, delta, delta_age_delta)
        shared = other_ns
      else:
        if shared:
          print '%s was shared, but is now clear: %s (%s, %s)' % (self, ref_hostname, delta, delta_age_delta)
        return False
      
    if not checked:
      self.disabled = "Failed to test %s wildcard caches"  % len(other_ns.cache_checks)
    
    print "%s is SHARED to %s" % (self, shared)
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
        if self.is_system:
          print
          print "* System DNS is broken: %s [%s] failed %s: %s <%s>" % (self.name, self.ip, test.__name__, warning, duration)
          print
        self.warnings.add(warning)
      if is_broken:
        # Do not disable internal nameservers, as it is nice to compare them!
        if not self.is_system:
          self.disabled = 'Failed %s: %s' % (test.__name__, warning)
        break

#    if self.warnings:
#      print '%s [%s] - %s' % (self.name, self.ip, self.warnings)
    return self.disabled

