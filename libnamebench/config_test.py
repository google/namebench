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

"""Tests for the config module."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import unittest
import config

class ConfigTest(unittest.TestCase):
  def testParseFullLine(self):
    line = '129.250.35.251=NTT (2)                               # y.ns.gin.ntt.net,39.569,-104.8582 (Englewood/CO/US)'
    expected = {'name': 'NTT (2)', 'service': 'NTT', 'ip': '129.250.35.251',
                'lon': '-104.8582', 'instance': '2', 'country_code': 'US',
                'lat': '39.569'}
    self.assertEquals(config._ParseServerLine(line), expected)

  def testOpenDNSLine(self):
    line = '208.67.220.220=OpenDNS                               # resolver2.opendns.com'
    expected = {'name': 'OpenDNS', 'service': 'OpenDNS', 'ip': '208.67.220.220',
                'lon': None, 'instance': None, 'country_code': None,
                'lat': None}

    self.assertEquals(config._ParseServerLine(line), expected)

  def testLineWithNoRegion(self):
    line = '4.2.2.2=Level/GTEI-2 (3)                             # vnsc-bak.sys.gtei.net,38.0,-97.0 (US) '
    expected = {'name': 'Level/GTEI-2 (3)', 'service': 'Level/GTEI-2',
                'ip': '4.2.2.2', 'lon': '-97.0', 'instance': '3',
                'country_code': 'US', 'lat': '38.0'}
    self.assertEquals(config._ParseServerLine(line), expected)

if __name__ == '__main__':
  unittest.main()
