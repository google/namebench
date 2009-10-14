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
    averages = dict([(x[0].ip, x[1]) for x in b.ComputeAverages()])
    self.assertEquals(len(averages), 4)
    self.assertTrue(averages[mocks.GOOD_IP] >= 8)
    self.assertTrue(averages[mocks.PERFECT_IP] <= 5)
    self.assertTrue(averages[mocks.BROKEN_IP] >= 59)
    self.assertTrue(averages[mocks.SLOW_IP] >= 20)
    self.assertEquals(b.BestOverallNameServer(), ns_list[1])
    self.assertEquals(b.NearestNameServers(count=2), [ns_list[1], ns_list[0]])


  def testDigestion(self):
    ns_list = (mocks.MockNameServer(mocks.GOOD_IP),
               mocks.MockNameServer(mocks.PERFECT_IP),
               mocks.MockNameServer(mocks.BROKEN_IP),
               mocks.MockNameServer(mocks.SLOW_IP))
    b = benchmark.Benchmark(ns_list)
    good = ns_list[0].FakeAnswer(None)
    bad = ns_list[0].FakeAnswer(None, no_answer=True)

    b.results = {
     ns_list[0]: [[('www.google.com.', 'A', 2.90, bad),
                   ('google.com.', 'A', 9.80, good),
                   ('www.google.com.', 'A', 9.90, good)],
                 [('www.google.com.', 'A', 9.90, bad),
                  ('google.com.', 'A', 9.90, good),
                  ('www.google.com.', 'A', 9.80, good)]],
     ns_list[1]: [[('www.google.com.', 'A', 3.40, good),
                   ('google.com.', 'A', 3.40, good),
                   ('www.google.com.', 'A', 3.60, good)],
                  [('www.google.com.', 'A', 3.30, good),
                   ('google.com.', 'A', 3.30, good),
                   ('www.google.com.', 'A', 3.40, good)]],
     ns_list[2]: [[('www.google.com.', 'A', 60, None),
                   ('google.com.', 'A', 60, None),
                   ('www.google.com.', 'A', 60, None)],
                   [('www.google.com.', 'A', 60, None),
                    ('google.com.', 'A', 60, None),
                    ('www.google.com.', 'A', 60, None)]],
     ns_list[3]: [[('www.google.com.', 'A', 26.25, good),
                   ('google.com.', 'A', 26.30, good),
                   ('www.google.com.', 'A', 26.10, good)],
                  [('www.google.com.', 'A', 26.40, good),
                   ('google.com.', 'A', 12.40, bad),
                   ('www.google.com.', 'A', 26.80, good)]]}

    expected = []
    averages = dict([(x[0].ip, x[1]) for x in b.ComputeAverages()])
    self.assertEquals(averages[mocks.GOOD_IP], 8.7000000000000011)
    self.assertEquals(averages[mocks.PERFECT_IP], 3.4000000000000004)
    self.assertEquals(averages[mocks.BROKEN_IP], 60)
    self.assertEquals(averages[mocks.SLOW_IP],24.041666666666664)

    expected = [('127.127.127.127', 3.2999999999999998),
                ('127.0.0.1', 9.80),
                ('9.9.9.9', 26.10),
                ('192.168.0.1', 60)]
    fastest = [(x[0].ip, x[1]) for x in b.FastestNameServerResult()]
    self.assertEquals(fastest, expected)

    expected = [
        (None, '####', 3.2999999999999998),
        (None, '##########', 9.8000000000000007),
        (None, '###########################', 26.100000000000001),
        (None, '############################################################',
         60)
    ]
    self.assertEquals(b._LowestLatencyAsciiChart(), expected)

if __name__ == '__main__':
  unittest.main()
