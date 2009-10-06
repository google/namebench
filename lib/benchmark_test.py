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

"""Tests for the benchmark module."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import unittest
import benchmark
import mocks

class BenchmarkTest(unittest.TestCase):
  def testCreateTestsWeighted(self):
    b = benchmark.Benchmark([mocks.MockNameServer(mocks.GOOD_IP)],
                            test_count=1000)
    results = b.CreateTests(('google.com', 'live.com'))
    self.assertEquals(len(results), 1000)
    self.assertTrue(('A', 'www.google.com.') in results)
    caches = [x for x in results if 'cache' in x[1]]
    self.assertTrue(len(caches) > 0 and len(caches) < 50)

  def testCreateTestsSingle(self):
    b = benchmark.Benchmark([mocks.MockNameServer(mocks.GOOD_IP)],
                            test_count=1)
    results = b.CreateTests(('A mail.google.com',))
    self.assertEquals(results, [['A', 'mail.google.com']])
    # Oops, this isn't a real tuple.
    self.assertRaises(AssertionError, b.CreateTests, 'google.com')

  def testCreateTestsChunkRecords(self):
    b = benchmark.Benchmark([mocks.MockNameServer(mocks.GOOD_IP)],
                            test_count=100)
    results = b.CreateTests(('A mail.google.com', 'CNAME test.live.com'),
                            select_mode='chunk')
    self.assertEquals(results, [['A', 'mail.google.com'],
                                ['CNAME', 'test.live.com']])

  def testEmptyRun(self):
    ns_list = (mocks.MockNameServer(mocks.GOOD_IP),)
    b = benchmark.Benchmark(ns_list, test_count=3, run_count=2)
    self.assertRaises(AssertionError, b.Run)

  def testRun(self):
    ns_list = (mocks.MockNameServer(mocks.GOOD_IP),
               mocks.MockNameServer(mocks.PERFECT_IP),
               mocks.MockNameServer(mocks.BROKEN_IP),
               mocks.MockNameServer(mocks.SLOW_IP))
    b = benchmark.Benchmark(ns_list, test_count=3, run_count=2)
    self.assertRaises(AssertionError, b.Run)
    b.CreateTests(['A www.google.com'])
    self.assertEquals(b.test_data,  [['A', 'www.google.com'],
                                     ['A', 'www.google.com'],
                                     ['A', 'www.google.com']])
    b.Run()
    ips_tested = sorted([ x.ip for x in b.results ])
    expected = ['127.0.0.1', '127.127.127.127', '192.168.0.1', '9.9.9.9']
    self.assertEquals(ips_tested, expected)
    self.assertEquals(len(b.results[ns_list[0]]), 2)
    self.assertEquals(len(b.results[ns_list[0]][0]), 3)

  def testNormalRun(self):
    ns_list = (mocks.MockNameServer(mocks.GOOD_IP),
               mocks.MockNameServer(mocks.PERFECT_IP),
               mocks.MockNameServer(mocks.BROKEN_IP),
               mocks.MockNameServer(mocks.SLOW_IP))
    b = benchmark.Benchmark(ns_list, test_count=3, run_count=2)
    b.CreateTests(['google.com', 'live.com'])
    b.Run()
    expected = ['127.0.0.1', '127.127.127.127', '192.168.0.1', '9.9.9.9']
    averages = [round(x[1]/3) for x in b.ComputeAverages()]
    print averages
    self.assertEquals(len(averages), 4)
    self.assertTrue(averages[0] >= 3) # GOOD
    self.assertTrue(averages[1] <= 2) # PERFECT
    self.assertTrue(averages[2] >= 19) # BROKEN
    self.assertTrue(averages[3] >= 9) # SLOW

    self.assertEquals(b.BestOverallNameServer(), ns_list[1])
    self.assertEquals(b.NearestNameServers(count=2), [ns_list[1], ns_list[0]])

if __name__ == '__main__':
  unittest.main()
