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

"""Tests for NameBench and basic methods."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import datetime
import unittest
import mocks
import benchmark

class TestBenchmark(unittest.TestCase):
  def testFindUsableNameServers(self):
    """Test automagic nameserver discovery and validation."""
    mock = mocks.MockNameBench('mock')
    mock.FindUsableNameServers()
    expected = {'10.0.0.1': '10.0.0.1', '192.168.1.2': 'Test 2'}
    self.assertEqual(mock.nameservers, expected)

  def testGenerateTestRecords(self):
    mock = mocks.MockNameBench('mock')
    domains = ['slashdot.org', 'google.com', 'x.gov']
    self.assertTrue(('A', 'www.slashdot.org.') or ('A', 'slashdot.org.')
                    in mock.GenerateTestRecords(domains, 3))
    self.assertTrue(('A', 'www.google.com.') or ('A', 'google.com.')
                    in mock.GenerateTestRecords(domains, 3))
    self.assertEqual(len(mock.GenerateTestRecords(domains, 3)), 3)

  def testTimedDNSRequest(self):
    mock = mocks.MockNameBench('mock')
    (response, duration) = mock.TimedDNSRequest('10.0.0.1', 'A', 'google.com.')
    self.assertEquals(len(response.answer), 1)
    self.assertEquals(duration, 9.0)

    (response, duration) = mock.TimedDNSRequest('192.168.1.2', 'A', 'x.gov.')
    self.assertEquals(duration, 22.5)
    self.assertEquals(len(response.answer), 0)

  def testBenchmarkNameServer(self):
    mock = mocks.MockNameBench('mock', test_count=3)
    tests = [('A', 'www.slashdot.org.'),
             ('A', 'www.google.com.'),
             ('A', 'x.gov.')]
    expected = [('www.slashdot.org.', 'A', 9.0, 0, -1),
                ('www.google.com.', 'A', 9.0, 1, 0),
                ('x.gov.', 'A', 9.0, 0, -1)]
    self.assertEquals(mock.BenchmarkNameServer('10.0.0.1', tests), expected)

    expected = [('www.slashdot.org.', 'A', 22.5, 0, -1),
                ('www.google.com.', 'A', 22.5, 1, 0),
                ('x.gov.', 'A', 22.5, 0, -1)]
    self.assertEquals(mock.BenchmarkNameServer('192.168.1.2', tests),
                      expected)

  def testSingleRunComputeAverages(self):
    mock = mocks.MockNameBench('mock', run_count=1)
    mock.Run()
    expected = [('10.0.0.1', 9.0, [9.0], 0),
                ('192.168.1.2', 22.5, [22.5], 0)]
    self.assertEquals(list(mock.ComputeAverages()), expected)

  def testMultipleRunComputeAverages(self):
    mock = mocks.MockNameBench('mock', run_count=2)
    mock.Run()
    expected = [('10.0.0.1', 9.0, [9.0, 9.0], 0),
                ('192.168.1.2', 22.5, [22.5, 22.5], 0)]
    self.assertEquals(list(mock.ComputeAverages()), expected)

    mock = mocks.MockNameBench('mock', run_count=3)
    mock.Run()
    expected = [('10.0.0.1', 9.0, [9.0, 9.0, 9.0], 0),
                ('192.168.1.2', 22.5, [22.5, 22.5, 22.5], 0)]
    self.assertEquals(list(mock.ComputeAverages()), expected)

  def testDigestedResults(self):
    mock = mocks.MockNameBench('mock', run_count=2, test_count=4)
    mock.Run()
    expected = [('10.0.0.1', [9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0]),
                ('Test 2', [22.5, 22.5, 22.5, 22.5, 22.5, 22.5, 22.5, 22.5])]
    self.assertEquals(mock.DigestedResults(), expected)

  def testFastestNameServerResult(self):
    mock = mocks.MockNameBench('mock', run_count=2, test_count=4)
    mock.Run()
    expected = [('10.0.0.1', 9.0), ('Test 2', 22.5)]
    self.assertEquals(list(mock.FastestNameServerResult()), expected)

if __name__ == '__main__':
  unittest.main()
