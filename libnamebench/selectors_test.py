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

"""Tests for the selector module."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import selectors
import unittest



class SelectorsTest(unittest.TestCase):
  def testMaxRepeatCount(self):
    self.assertEquals(selectors.MaxRepeatCount(range(1,10), 5),
                      selectors.MAX_REPEAT)
    self.assertEquals(selectors.MaxRepeatCount(range(1,10), 50),
                      2**32)

  def testRandomSelect(self):
    elements = range(10)
    result = selectors.RandomSelect(elements, 10)
    self.assertEquals(len(result), 10)
    self.assertNotEquals(result, range(10))

  def testRandomSelectConstrained(self):
    elements = range(5)
    result = selectors.RandomSelect(elements, 10)
    self.assertEquals(len(result), 10)
    ones = [x for x in result if x == 1]
    twos = [x for x in result if x == 2]
    self.assertTrue(len(ones) <= selectors.MAX_REPEAT)
    self.assertTrue(len(twos) <= selectors.MAX_REPEAT)

  def testRandomSelectVeryConstrained(self):
    """Test to make sure we don't infinite loop if count > len(elements)*3"""
    elements = range(2)
    result = selectors.RandomSelect(elements, 20)
    self.assertEquals(len(result), 20)
    ones = [x for x in result if x == 1]
    twos = [x for x in result if x == 2]
    self.assertTrue(ones > selectors.MAX_REPEAT)
    self.assertTrue(twos > selectors.MAX_REPEAT)

  def testWeightedDistribution(self):
    """Ensure that a weighted distribution is indeed weighted."""
    elements = range(20)
    result = selectors.WeightedDistribution(elements, 10)
    self.assertEquals(len(result), 10)
    zeros = [x for x in result if x == 0]
    ones = [x for x in result if x == 1]
    low = [x for x in result if x < 3]
    mid = [x for x in result if x > 7 and x < 13]
    high = [x for x in result if x > 17]
    self.assertTrue(len(zeros) <= selectors.MAX_REPEAT)
    self.assertTrue(len(ones) <= selectors.MAX_REPEAT)
    self.assertTrue(len(low) >= 3)
    self.assertTrue(len(mid) <= 3)
    self.assertTrue(len(high) <= 2)

  def testChuckSelect(self):
    elements = range(10000)
    result = selectors.ChunkSelect(elements, 5)
    self.assertEquals(len(result), 5)
    # Make sure our segment is a subset
    self.assertTrue(set(result).issubset(set(elements)))

    # Make sure our segment is contiguous
    self.assertEquals(result, range(result[0], result[0]+5))


    result2 = selectors.ChunkSelect(elements, 5)
    self.assertEquals(len(result), 5)
    self.assertNotEquals(result, result2)


  def testChunkSelectConstrained(self):
    """Make sure we aren't inventing bogus data."""
    elements = range(20)
    result = selectors.ChunkSelect(elements, 25)
    self.assertEquals(len(result), 20)
    self.assertEquals(elements, result)



if __name__ == '__main__':
  unittest.main()
