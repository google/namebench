#!/usr/bin/env python
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

"""Mocks for tests."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import mocks
import nameserver
import unittest

class TestNameserver(unittest.TestCase):
  def testInit(self):
    ns = mocks.MockNameServer(mocks.GOOD_IP)
    self.assertEquals(ns.ip, mocks.GOOD_IP)
    self.assertEquals(ns.name, None)

    ns = mocks.MockNameServer(mocks.NO_RESPONSE_IP, name='Broked')
    self.assertEquals(ns.ip, mocks.NO_RESPONSE_IP)
    self.assertEquals(ns.name, 'Broked')


  def testTimedRequest(self):
    ns = mocks.MockNameServer(mocks.GOOD_IP)
    (response, duration, exception) = ns.TimedRequest('A', 'www.paypal.com')
    self.assertEquals(response.id, 999)
    expected = ('www.paypal.com. 159 IN A 66.211.169.65\n'
                'www.paypal.com. 159 IN A 66.211.169.2')
    self.assertEquals(str(response.answer[0]), expected)
    self.assertTrue(duration > 0)
    self.assertEquals(exception, None)

  def testTestAnswers(self):
     ns = mocks.MockNameServer(mocks.GOOD_IP)
     (is_broken, warning, duration) = ns.TestAnswers('A', 'www.paypal.com',
                                                     '10.0.0.1')
     self.assertEquals(is_broken, False)
     self.assertEquals(warning, None)
     self.assertTrue(duration > 0 and duration < 3600)

  def testResponseToAscii(self):
    ns = mocks.MockNameServer(mocks.GOOD_IP)
    (response, duration, exception) = ns.TimedRequest('A', 'www.paypal.com')
    self.assertEquals(nameserver.ResponseToAscii(response),
                      '66.211.169.65 + 66.211.169.2')
    response.answer = None
    self.assertEquals(nameserver.ResponseToAscii(response), 'no answer')

  def testGoogleComResponse(self):
    ns = mocks.MockNameServer(mocks.GOOD_IP)
    (is_broken, warning, duration) = ns.TestGoogleComResponse()
    self.assertEquals(is_broken, False)
    self.assertEquals(warning,
                      'google.com. is hijacked (66.211.169.65 + 66.211.169.2)')
    self.assertTrue(duration > 0 and duration < 3600)

  def testWwwGoogleComResponse(self):
    ns = mocks.MockNameServer(mocks.GOOD_IP)
    (is_broken, warning, duration) = ns.TestWwwGoogleComResponse()
    self.assertEquals(is_broken, True)
    self.assertEquals(warning, 'No answer')
    self.assertTrue(duration > 0 and duration < 3600)

  def testWwwPaypalComResponse(self):
    ns = mocks.MockNameServer(mocks.GOOD_IP)
    (is_broken, warning, duration) = ns.TestWwwPaypalComResponse()
    self.assertEquals(is_broken, False)
    self.assertEquals(warning, None)

  def testNegativeResponse(self):
    ns = mocks.MockNameServer(mocks.NO_RESPONSE_IP)
    (is_broken, warning, duration) = ns.TestNegativeResponse()
    self.assertEquals(is_broken, False)
    self.assertEquals(warning, None)

  def testNegativeResponseHijacked(self):
    ns = mocks.MockNameServer(mocks.GOOD_IP)
    (is_broken, warning, duration) = ns.TestNegativeResponse()
    self.assertEquals(is_broken, False)
    self.assertEquals(warning,
                      'NXDOMAIN Hijacking (66.211.169.65 + 66.211.169.2)')

  def testNegativeResponseBroken(self):
    ns = mocks.MockNameServer(mocks.BROKEN_IP)
    (is_broken, warning, duration) = ns.TestNegativeResponse()
    self.assertEquals(is_broken, True)
    self.assertEquals(warning, 'BadResponse')

  def testWildcardCache(self):
    ns = mocks.MockNameServer(mocks.GOOD_IP)
    (response, is_broken, warning, duration) = ns.QueryWildcardCache()
    self.assertEquals(is_broken, False)
    question = str(response.question[0])
    self.assertTrue(question.startswith('namebench'))
    self.assertEquals(warning, None)

  def testCheckHealthGood(self):
    ns = mocks.MockNameServer(mocks.GOOD_IP)
    ns.CheckHealth()
    self.assertEquals(ns.CheckHealth(), False)
    self.assertEquals(ns.warnings, ['No answer'])
    self.assertEquals(len(ns.checks), 1)
    self.assertEquals(ns.failure[0], 'TestWwwGoogleComResponse')
    self.assertEquals(ns.checks[0][0:3],
                      ('TestWwwGoogleComResponse', True, 'No answer'))

  def testCheckHealthPerfect(self):
    ns = mocks.MockNameServer(mocks.PERFECT_IP)
    ns.CheckHealth()
    self.assertEquals(ns.CheckHealth(), True)
    expected = ['www.google.com. is hijacked (66.211.169.65 + 66.211.169.2)',
                'google.com. is hijacked (66.211.169.65 + 66.211.169.2)',
                'NXDOMAIN Hijacking (66.211.169.65 + 66.211.169.2)']
    self.assertEquals(ns.warnings, expected)
    self.assertEquals(len(ns.checks), 5)
    self.assertEquals(ns.failure, None)
    self.assertTrue(ns.check_duration > 10)

  def testQUeryWildcardCacheSaving(self):
    ns = mocks.MockNameServer(mocks.GOOD_IP)
    other_ns = mocks.MockNameServer(mocks.PERFECT_IP)
    ns.QueryWildcardCache(save=True)
    other_ns.QueryWildcardCache(save=True)

    # Test our cache-sharing mechanisms
    (hostname, ttl) = ns.cache_check
    self.assertTrue(hostname.startswith('namebench'))
    self.assertEquals(ttl, 159)
    (other_hostname, other_ttl) = other_ns.cache_check
    self.assertTrue(other_hostname.startswith('namebench'))
    self.assertNotEqual(hostname, other_hostname)
    self.assertEquals(other_ttl, 159)

  def testSharedCacheNoMatch(self):
    ns = mocks.MockNameServer(mocks.GOOD_IP)
    other_ns = mocks.MockNameServer(mocks.PERFECT_IP)
    ns.QueryWildcardCache(save=True)
    other_ns.QueryWildcardCache(save=True)
    (shared, slower, faster) = ns.TestSharedCache(other_ns)
    self.assertEquals(shared, False)
    self.assertEquals(slower, None)
    self.assertEquals(faster, None)


  def testSharedCacheMatch(self):
    ns = mocks.MockNameServer(mocks.GOOD_IP)
    other_ns = mocks.MockNameServer(mocks.PERFECT_IP)
    ns.QueryWildcardCache(save=True)
    other_ns.QueryWildcardCache(save=True)
    # Increase the TTL of 'other'
    other_ns.cache_check = (other_ns.cache_check[0], other_ns.cache_check[1] + 5)
    (shared, slower, faster) = ns.TestSharedCache(other_ns)
    self.assertEquals(shared, True)
    self.assertEquals(slower.ip, mocks.GOOD_IP)
    self.assertEquals(faster.ip, mocks.PERFECT_IP)


    # Increase the TTL of 'other' by a whole lot
    other_ns.cache_check = (other_ns.cache_check[0], other_ns.cache_check[1] + 3600)
    (shared, slower, faster) = ns.TestSharedCache(other_ns)
    self.assertEquals(shared, False)
    self.assertEquals(slower, None)
    self.assertEquals(faster, None)


if __name__ == '__main__':
  unittest.main()
