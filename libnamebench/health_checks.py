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


"""Module for all nameserver health checks."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import random
import sys
import time
import util

from dns import rcode

WILDCARD_DOMAINS = ('live.com.', 'blogspot.com.', 'wordpress.com.')
LIKELY_HIJACKS = ['www.google.com.', 'windowsupdate.microsoft.com.', 'www.paypal.com.']

# How many checks to consider when calculating ns check_duration
SHARED_CACHE_TIMEOUT_MULTIPLIER = 1.25
ROOT_SERVER_TIMEOUT_MULTIPLIER = 0.5
CENSORSHIP_TIMEOUT = 30
MAX_STORE_ATTEMPTS = 4
TOTAL_WILDCARDS_TO_STORE = 3

FATAL_RCODES = ['REFUSED', 'NOTAUTH']

class NameServerHealthChecks(object):
  """Health checks for a nameserver."""

  def TestAnswers(self, record_type, record, expected, critical=False, timeout=None):
    """Test to see that an answer returns correct IP's.

    Args:
      record_type: text record type for NS query (A, CNAME, etc)
      record: string to query for
      expected: tuple of strings expected in all answers
      critical: If this query fails, should it count against the server.
      timeout: timeout for query in seconds (int)

    Returns:
      (is_broken, error_msg, duration)
    """
    is_broken = False
    unmatched_answers = []
    if not timeout:
      timeout = self.health_timeout
    (response, duration, error_msg) = self.TimedRequest(record_type, record, timeout)
    if response:
      response_code = rcode.to_text(response.rcode())
      if response_code in FATAL_RCODES:
        error_msg = 'Responded with: %s' % response_code
        if critical:
          is_broken = True
      elif not response.answer:
        # Avoid preferring broken DNS servers that respond quickly
        duration = util.SecondsToMilliseconds(self.health_timeout)
        error_msg = 'No answer (%s): %s' % (response_code, record)
        is_broken = True
      else:
        found_usable_record = False
        for answer in response.answer:
          if found_usable_record:
            break

          # Process the first sane rdata object available in the answers
          for rdata in answer:
            # CNAME
            if rdata.rdtype == 5:
              reply = str(rdata.target)
            # A Record
            elif rdata.rdtype == 1:
              reply = str(rdata.address)
            else:
              continue

            found_usable_record = True
            found_match = False
            for string in expected:
              if reply.startswith(string) or reply.endswith(string):
                found_match = True
                break
            if not found_match:
              unmatched_answers.append(reply)

        if unmatched_answers:
          hijack_text = ', '.join(unmatched_answers).rstrip('.')
          if record in LIKELY_HIJACKS:
            error_msg = '%s is hijacked: %s' % (record.rstrip('.'), hijack_text)
          else:
            error_msg = '%s appears incorrect: %s' % (record.rstrip('.'), hijack_text)
    else:
      if not error_msg:
        error_msg = 'No response'
      is_broken = True

    return (is_broken, error_msg, duration)

  def TestBindVersion(self):
    """Test for BIND version. This acts as a pretty decent ping."""
    _, duration = self.GetVersion()
    return (False, None, duration)

  def TestNodeId(self):
    """Get the current node id."""
    self.GetNodeIdWithDuration()
    return (False, False, 0.0)

  def TestNegativeResponse(self, prefix=None):
    """Test for NXDOMAIN hijaaking."""
    is_broken = False
    if prefix:
      hostname = prefix
      warning_suffix = ' (%s)' % prefix
    else:
      hostname = 'test'
      warning_suffix = ''
    poison_test = '%s.nb%s.google.com.' % (hostname, random.random())
    (response, duration, error_msg) = self.TimedRequest('A', poison_test,
                                                        timeout=self.health_timeout*2)
    if not response:
      if not error_msg:
        error_msg = 'No response'
      is_broken = True
    elif response.answer:
      error_msg = 'NXDOMAIN Hijacking' + warning_suffix

    return (is_broken, error_msg, duration)


  def TestWwwNegativeResponse(self):
    return self.TestNegativeResponse(prefix='www')

  def TestARootServerResponse(self):
    return self.TestAnswers('A', 'a.root-servers.net.', '198.41.0.4', critical=True)

  def StoreWildcardCache(self):
    """Store a set of wildcard records."""
    timeout = self.health_timeout * SHARED_CACHE_TIMEOUT_MULTIPLIER
    attempted = []
    self.cache_checks = []

    while len(self.cache_checks) != TOTAL_WILDCARDS_TO_STORE:
      if len(attempted) == MAX_STORE_ATTEMPTS:
        self.DisableWithMessage('Unable to get uncached results for: %s' % ', '.join(attempted))
        return False
      domain = random.choice(WILDCARD_DOMAINS)
      hostname = 'namebench%s.%s' % (random.randint(1, 2**32), domain)
      attempted.append(hostname)
      response = self.TimedRequest('A', hostname, timeout=timeout)[0]
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

    if self.is_disabled or other_ns.is_disabled:
      return False

    if not other_ns.cache_checks:
      print '%s has no cache checks (disabling - how did this happen?)' % other_ns
      other_ns.DisableWithMessage('Unable to perform cache checks.')
      return False

    for (ref_hostname, ref_response, ref_timestamp) in other_ns.cache_checks:
      response = self.TimedRequest('A', ref_hostname, timeout=timeout)[0]
      # Retry once - this *may* cause false positives however, as the TTL may be updated.
      if not response or not response.answer:
        sys.stdout.write('x')
        response = self.TimedRequest('A', ref_hostname, timeout=timeout)[0]

      if response and response.answer:
        ref_ttl = ref_response.answer[0].ttl
        ttl = response.answer[0].ttl
        delta = abs(ref_ttl - ttl)
        query_age = self.timer() - ref_timestamp
        delta_age_delta = abs(query_age - delta)

        if delta > 0 and delta_age_delta < 2:
          return other_ns
      else:
        sys.stdout.write('!')
      checked.append(ref_hostname)

    if not checked:
      self.AddFailure('Failed to test %s wildcard caches'  % len(other_ns.cache_checks))
    return shared

  def CheckCensorship(self, tests):
    """Check to see if results from a nameserver are being censored."""
    for (check, expected) in tests:
      (req_type, req_name) = check.split(' ')
      expected_values = expected.split(',')
      is_broken, warning = self.TestAnswers(req_type.upper(), req_name, expected_values,
                                            timeout=CENSORSHIP_TIMEOUT)[0:2]
      if is_broken:
        is_broken, warning = self.TestAnswers(req_type.upper(), req_name, expected_values,
                                              timeout=CENSORSHIP_TIMEOUT)[0:2]
      if warning:
        self.AddWarning(warning, penalty=False)

  def CheckHealth(self, sanity_checks=None, fast_check=False, final_check=False, port_check=False):
    """Qualify a nameserver to see if it is any good."""

    is_fatal = False
    if fast_check:
      tests = [(self.TestARootServerResponse, [])]
      is_fatal = True
      sanity_checks = []
    elif final_check:
      tests = [(self.TestWwwNegativeResponse, []), (self.TestNodeId, [])]
    elif port_check:
      tests = [(self.TestNodeId, [])]
    else:
      # Put the bind version here so that we have a great minimum latency measurement.
      tests = [(self.TestNegativeResponse, []), (self.TestBindVersion, [])]

    if sanity_checks:
      for (check, expected_value) in sanity_checks:
        (req_type, req_name) = check.split(' ')
        expected_values = expected_value.split(',')
        tests.append((self.TestAnswers, [req_type.upper(), req_name, expected_values]))

    for test in tests:
      (function, args) = test
      (is_broken, warning, duration) = function(*args)
      if args:
        test_name = args[1]
      else:
        test_name = function.__name__

      self.checks.append((test_name, is_broken, warning, duration))
      if is_broken:
        self.AddFailure('%s: %s' % (test_name, warning), fatal=is_fatal)
      if warning:
        # Special case for NXDOMAIN de-duplication
        if not ('NXDOMAIN' in warning and 'NXDOMAIN Hijacking' in self.warnings):
          self.AddWarning(warning)
      if self.is_disabled:
        break

    return self.is_disabled

