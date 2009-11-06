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
import util
import unittest


class TestBasicMethods(unittest.TestCase):
  def testTimeDeltaToMilliseconds(self):
    delta = datetime.timedelta(days=1)
    self.assertEqual(util.TimeDeltaToMilliseconds(delta), 86400000)

    delta = datetime.timedelta(0, 3, 248193)
    self.assertEqual(util.TimeDeltaToMilliseconds(delta),
                     3248.1930000000002)

  def testCalculateListAverage(self):
    self.assertEqual(util.CalculateListAverage([3, 2, 2]),
                     2.3333333333333335)

  def testDrawTextBar(self):
    self.assertEqual(util.DrawTextBar(1, 10, max_width=10), '#')
    self.assertEqual(util.DrawTextBar(5, 10, max_width=10), '#####')
    self.assertEqual(util.DrawTextBar(5, 5, max_width=5), '#####')
    # Make sure to draw at least something!
    self.assertEqual(util.DrawTextBar(0.05, 10, max_width=10), '#')

  def testInternalNameServers(self):
    self.assertTrue(len(util.InternalNameServers()) > 0)
    self.assertTrue(len(util.InternalNameServers()) < 5)



if __name__ == '__main__':
  unittest.main()
