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
import socket
import sys
import time
import traceback

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
import dns.version

# Look for buggy system versions of namebench
if dns.version.hexversion < 17301744:
  raise ValueError("dnspython 1.8.0+ required, while %s was found. namebench has 1.8.0 built-in, so you can simply deinstall the system-wide version. It isn't thread-safe anyways." % dns.version.version)

import health_checks
import util

# Pick the most accurate timer for a platform. Stolen from timeit.py:
if sys.platform[:3] == 'win':
  DEFAULT_TIMER = time.clock
else:
  DEFAULT_TIMER = time.time


# How many failures before we disable system nameservers
MAX_NORMAL_FAILURES = 2
MAX_SYSTEM_FAILURES = 7
MAX_PREFERRED_FAILURES = 5

FAILURE_PRONE_RATE = 10

def ResponseToAscii(response):
  if not response:
    return None
  if response.answer:
    answers = [', '.join(map(str, x.items)) for x in response.answer]
    return ' -> '.join(answers)
  else:
    return dns.rcode.to_text(response.rcode())


class NameServer(health_checks.NameServerHealthChecks):
  """Hold information about a particular nameserver."""

  def __init__(self, ip, name=None, internal=False, preferred=False):
    self.name = name
    # We use _ for IPV6 representation in our configuration due to ConfigParser issues.
    self.ip = ip.replace('_', ':')
    self.is_system = internal
    self.is_regional = False
    self.is_global = False
    self.is_custom = False
    self.system_position = None
    self.is_preferred = preferred
    self.timeout = 6
    self.health_timeout = 6
    self.ping_timeout = 1
    self.ResetTestStatus()
    self.port_behavior = None
    self.timer = DEFAULT_TIMER

    if ':' in self.ip:
      self.is_ipv6 = True
    else:
      self.is_ipv6 = False

  @property
  def check_average(self):
    # If we only have a ping result, sort by it. Otherwise, use all non-ping results.
    if len(self.checks) == 1:
      return self.checks[0][3]
    else:
      return util.CalculateListAverage([x[3] for x in self.checks[1:]])
    
  @property
  def fastest_check_duration(self):
    if self.checks:
      return min([x[3] for x in self.checks])
    else:
      return 0.0

  @property
  def slowest_check_duration(self):
    if self.checks:
      return max([x[3] for x in self.checks])
    else:
      return None

  @property
  def check_duration(self):
    return sum([x[3] for x in self.checks])

  @property
  def warnings_string(self):
    if self.disabled:
      return '(excluded: %s)' % self.disabled
    else:
      return ', '.join(map(str, self.warnings))

  @property
  def warnings_comment(self):
    if self.warnings or self.disabled:
      return '# ' + self.warnings_string
    else:
      return ''

  @property
  def errors(self):
    return ['%s (%s requests)' % (_[0], _[1]) for _ in self.error_map.items() if _[0] != 'Timeout']

  @property
  def error_count(self):
    return sum([_[1] for _ in self.error_map.items() if _[0] != 'Timeout'])
    
  @property
  def timeout_count(self):
    return self.error_map.get('Timeout', 0)
    
  @property
  def notes(self):
    _notes = []
    if self.system_position == 0:
      _notes.append('The current preferred DNS server.')
    elif self.system_position:
      _notes.append('A backup DNS server for this system.')
    if self.is_failure_prone:
      _notes.append('%0.0f queries to this host failed' % self.failure_rate)
    if self.port_behavior and 'POOR' in self.port_behavior:
      _notes.append('Vulnerable to cache poisoning attacks (poor randomization)')
    if self.disabled:
      _notes.append(self.disabled)
    else:
      _notes.extend(self.warnings)
    if self.errors:
      _notes.extend(self.errors)
    return _notes

  @property
  def hostname(self):
    if hasattr(self, '_cached_hostname'):
      return self._cached_hostname
    
    try:
      answer = dns.resolver.query(dns.reversename.from_address(self.ip), 'PTR')
      if answer:
        self._cached_hostname = str(answer[0]).rstrip('.')
    except:
      self._cached_hostname = ''
    return self._cached_hostname

  @property
  def is_failure_prone(self):
    if self.failure_rate >= FAILURE_PRONE_RATE:
      return True
    else:
      return False

  @property
  def failure_rate(self):
    if not self.failure_count or not self.request_count:
      return 0
    else:
      return (float(self.failure_count) / float(self.request_count)) * 100

  def __str__(self):
    return '%s [%s]' % (self.name, self.ip)

  def __repr__(self):
    return self.__str__()

  def ResetTestStatus(self):
    """Reset testing status of this host."""    
    self.warnings = set()
    self.shared_with = set()
    self.disabled = False
    self.checks = []
    self.failed_test_count = 0
    self.share_check_count = 0
    self.cache_checks = []
    self.is_slower_replica = False
    self.ResetErrorCounts()
    
  def ResetErrorCounts(self):
    """NOTE: This gets called by benchmark.Run()!"""
    
    self.request_count = 0
    self.failure_count = 0
    self.error_map = {}

  def AddFailure(self, message):
    """Add a failure for this nameserver. This will effectively disable it's use."""
    if self.is_system:
      max = MAX_SYSTEM_FAILURES
    elif self.is_preferred:
      max = MAX_PREFERRED_FAILURES
    else:
      max = MAX_NORMAL_FAILURES

    self.failed_test_count += 1

    if self.is_system or self.is_preferred:
      # If the preferred host is IPv6 and we have no previous checks, fail quietly.
      if self.is_ipv6 and len(self.checks) <= 1:
        self.disabled = message
      else:
        print "\n* %s failed test #%s/%s: %s" % (self, self.failed_test_count, max, message)

    if self.failed_test_count >= max:
      self.disabled = message

  def CreateRequest(self, record, request_type, return_type):
    """Function to work around any dnspython make_query quirks."""
    return dns.message.make_query(record, request_type, return_type)

  def Query(self, request, timeout):
    return dns.query.udp(request, self.ip, timeout, 53)

  def TimedRequest(self, type_string, record_string, timeout=None, rdataclass=None):
    """Make a DNS request, returning the reply and duration it took.

    Args:
      type_string: DNS record type to query (string)
      record_string: DNS record name to query (string)
      timeout: optional timeout (float)

    Returns:
      A tuple of (response, duration in ms [float], error_msg)

    In the case of a DNS response timeout, the response object will be None.
    """
    if not rdataclass:
      rdataclass = dns.rdataclass.IN
    else:
      rdataclass = dns.rdataclass.from_text(rdataclass)

    request_type = dns.rdatatype.from_text(type_string)
    record = dns.name.from_text(record_string, None)
    request = None
    self.request_count += 1

    # Sometimes it takes great effort just to craft a UDP packet.
    try:
      request = self.CreateRequest(record, request_type, rdataclass)
    except ValueError, exc:
      if not request:
        return (None, 0, util.GetLastExceptionString())

    if not timeout:
      timeout = self.timeout

    error_msg = None
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
      error_msg = util.GetLastExceptionString()
      response = None
    # This is pretty normal if someone runs namebench offline.
    except (socket.error):
      response = None
      if ':' in self.ip:
        error_msg = 'socket error: IPv6 may not be available.'
      else:
        error_msg = util.GetLastExceptionString()
    # Pass these exceptions up the food chain
    except (KeyboardInterrupt, SystemExit, SystemError), exc:
      raise exc
    except:
      error_msg = util.GetLastExceptionString()
      print "* Unusual error with %s:%s on %s: %s" % (type_string, record_string, self, error_msg)
      response = None

    if not response:
      self.failure_count += 1

    if not duration:
      duration = self.timer() - start_time

    if exc and not error_msg:
      error_msg = '%s: %s' % (record_string, util.GetLastExceptionString())
    
    if error_msg:
      key = util.GetLastExceptionString()
      self.error_map[key] = self.error_map.setdefault(key, 0) + 1

    return (response, util.SecondsToMilliseconds(duration), error_msg)


