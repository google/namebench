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

# How many checks to consider when calculating ns check_duration
SHARED_CACHE_TIMEOUT_MULTIPLIER = 4

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
    self.warnings = []
    self.shared_with = []
    self.disabled = False
    self.checks = []
    self.share_check_count = 0
    self.cache_check = None
    self.is_slower_replica = False

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
      start_time = timer()
      response = self.Query(request, timeout)
      duration = timer() - start_time
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
      duration = timer() - start_time

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

  def StoreWildcardCache(self):
    (is_broken, warning, duration) = self.QueryWildcardCache(save=True)[1:]
    if warning:
      self.warnings.append(warning)
    if is_broken:
      # Do not disable system DNS servers
      if self.is_system:
        print 'Ouch, %s failed StoreWildcardCache: %s <%s>' % (self, warning, duration)
      else:
        self.disabled = 'Failed CacheWildcard: %s' % warning

    # Is this really a good idea to count?
    #self.checks.append(('wildcard store', is_broken, warning, duration))

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

    # Is this really a good idea to count?
    #self.checks.append((cache_id, is_broken, warning, duration))

    if is_broken:
      if self.is_system:
        print 'Ouch, %s failed TestSharedCache: %s <%s>' % (self, warning, duration)
      else:
        self.disabled = 'Failed shared-cache: %s' % warning
    else:
      my_ttl = response.answer[0].ttl
      delta = abs(other_ttl - my_ttl)
      if delta > 0:
        if my_ttl < other_ttl:
          upstream = self
          upstream_ttl = my_ttl
          downstream_ttl = other_ttl
          downstream = other_ns
        else:
          upstream = other_ns
          downstream = self
          upstream_ttl = other_ttl
          downstream_ttl = my_ttl


        if other_ns.check_duration > self.check_duration:
          slower = other_ns
          faster = self
        else:
          slower = self
          faster = other_ns

        if delta > MIN_SHARING_DELTA_MS and delta < MAX_SHARING_DELTA_MS:
#          print "%s [%s] -> %s [%s] for %s" % (downstream, downstream_ttl,
#                                                         upstream, upstream_ttl, cache_id)
          return (True, slower, faster)

    return (False, None, None)

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
    self.checks = []
    self.warnings = []

    for test in tests:
      (is_broken, warning, duration) = test()
      self.checks.append((test.__name__, is_broken, warning, duration))
      if warning:
        if self.is_system:
          print
          print "* System DNS is broken: %s [%s] failed %s: %s <%s>" % (self.name, self.ip, test.__name__, warning, duration)
          print
        self.warnings.append(warning)
      if is_broken:
        # Do not disable internal nameservers, as it is nice to compare them!
        if not self.is_system:
          self.disabled = 'Failed %s: %s' % (test.__name__, warning)
        break

#    if self.warnings:
#      print '%s [%s] - %s' % (self.name, self.ip, self.warnings)
    return self.disabled

