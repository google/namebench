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

"""Tests for all functions related to chart generation."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import unittest
import nameserver
import charts


def _ExampleRunsData():
  odns = nameserver.NameServer('208.67.220.220', name='OpenDNS')
  udns = nameserver.NameServer('156.154.70.1', name='UltraDNS')
  data = [(odns, [79.0, 191.0, 84.0, 878.0, 82.0, 85.0, 882.0, 187.0, 79.0,
                  80.0, 79.0, 261.0, 79.0, 83.0, 82.0, 420.0, 822.0, 1890.0,
                  78.0, 79.0, 86.0, 89.0, 125.0, 94.0, 81.0, 79.0, 81.0, 79.0,
                  1105.0, 84.0]),
          (udns, [9.0, 8.0, 13.0, 329.0, 9.0, 9.0, 773.0, 52.0, 9.0, 8.0, 8.0,
                  143.0, 27.0, 104.0, 8.0, 8.0, 320.0, 594.0, 8.0, 312.0, 11.0,
                  9.0, 174.0, 83.0, 8.0, 9.0, 8.0, 8.0, 496.0, 533.0])]
  return data


# TODO(tstromberg): Clean up long lines, cleanse IP/hostnames.
class ChartFunctionsTest(unittest.TestCase):
  def testDarkenHexColorCode(self):
    self.assertEquals(charts.DarkenHexColorCode('ffffff', 0), 'ffffff')
    self.assertEquals(charts.DarkenHexColorCode('2c2c2c', 1), '0c0c0c')
    self.assertEquals(charts.DarkenHexColorCode('ff0000', 1), 'df0000')
    self.assertEquals(charts.DarkenHexColorCode('ff00ff', 2), 'bf00bf')

  def testGoodTicks(self):
    self.assertEquals(charts._GoodTicks(50), 5)
    self.assertEquals(charts._GoodTicks(9.8, tick_size=0.5, num_ticks=7), 2.0)


class BasicChartTests(unittest.TestCase):
  def testPerRunDurationBarGraph(self):
    sorted_averages = [
        ('10.0.0.1', [5.871, 2.6599]),
        ('192.168.1.2', [15.0867, 15.2531]),
        ('172.168.1.2', [70.7752, 15.02163]),
    ]
    results = charts.PerRunDurationBarGraph(sorted_averages)
    self.assertTrue('e%3AFBM48Y%2CCRNBM' in results)
    expected = (
        'http://chart.apis.google.com/chart?chxt=y%2Cx%2Cx&chd=e%3AFBM48Y%2'
        'CCRNBM0&chxp=2%2C31&chxr=1%2C0%2C75%7C2%2C-3.75%2C78.75&chxtc=1%2C-720'
        '&chco=4684ee%2C00248e&chbh=a&chs=720x130&cht=bhg&chxl=0%3A%7C'
        '172.168.1.2%7C192.168.1.2%7C10.0.0.1%7C1%3A%7C0%7C5%7C10%7C15%7C20'
        '%7C25%7C30%7C35%7C40%7C45%7C50%7C55%7C60%7C65%7C70%7C75%7C2%3A%7C'
        'Duration%20in%20ms.&chdl=Run%201%7CRun%202'
    )
    self.assertEqual(results, expected)

  def testMinimumDurationBarGraph(self):
    fastest = ((nameserver.NameServer('208.67.220.220', name='OpenDNS'), 10.0),
               (nameserver.NameServer('156.154.70.1', name='UltraDNS'), 15.75))

    expected = (
        'http://chart.apis.google.com/chart?chxt=y%2Cx%2Cx&chd=e%3AgAyZ&'
        'chxp=2%2C9&chxr=1%2C0%2C20%7C2%2C-1.0%2C21.0&chxtc=1%2C-720'
        '&chco=0000ff&chbh=a&chs=720x78&cht=bhg&chxl=0%3A%7CUltraDNS%7COpenDNS'
        '%7C1%3A%7C0%7C3%7C6%7C9%7C12%7C15%7C18%7C20%7C2%3A%7C'
        'Duration%20in%20ms.'
    )
    self.assertEquals(charts.MinimumDurationBarGraph(fastest), expected)

  def testMaximumRunDuration(self):
    runs_data = [
        ('G', [3.851, 4.7690, 423.971998, 189.674001, 14.477, 174.788001]),
        ('Y', [99.99, 488.88])
    ]
    self.assertEquals(charts._MaximumRunDuration(runs_data), 488.88)

class DistributionChartTests(unittest.TestCase):

  def testMakeCumulativeDistribution(self):
    runs_data = _ExampleRunsData()
    expected = [
        (runs_data[0][0],
         [(0, 0), (3.3333333333333335, 78.0),(26.666666666666668, 79.0),
          (30.0, 80.0), (36.666666666666664, 81.0), (43.333333333333336, 82.0),
          (46.666666666666664, 83.0), (53.333333333333336, 84.0),
          (56.666666666666664, 85.0), (60.0, 86.0), (63.333333333333329, 89.0),
          (66.666666666666657, 94.0), (70.0, 125.0), (73.333333333333329, 187.0),
          (76.666666666666671, 191.0), (80.0, 261.0), (83.333333333333343, 420.0),
          (86.666666666666671, 822.0), (90.0, 878.0), (93.333333333333329, 882.0),
          (96.666666666666671, 1105.0), (100, 1890.0)]),
        (runs_data[1][0],
         [(0, 0), (30.0, 8.0), (50.0, 9.0), (53.333333333333336, 11.0),
          (56.666666666666664, 13.0), (60.0, 27.0), (63.333333333333329, 52.0),
          (66.666666666666657, 83.0), (70.0, 104.0), (73.333333333333329, 143.0),
          (76.666666666666671, 174.0), (80.0, 312.0), (83.333333333333343, 320.0),
          (86.666666666666671, 329.0), (90.0, 496.0), (93.333333333333329, 533.0),
          (96.666666666666671, 594.0), (100, 773.0)])]
    self.assertEquals(charts._MakeCumulativeDistribution(runs_data), expected)

  def testDistributionLineGraph(self):
    runs_data = _ExampleRunsData()
    url = charts.DistributionLineGraph(runs_data, scale=350)
    expected = (
        'http://chart.apis.google.com/chart?cht=lxy&chs=720x410&chxt=x,y&'
        'chg=10,20&chxr=0,0,350|1,0,100&chd=t:0,22,23,23,23,23,24,24,24,25,25'
        ',27,36,53,55,75,120|0,3,27,30,37,43,47,53,57,60,63,67,70,73,77,80,83|'
        '0,2,3,3,4,8,15,24,30,41,50,89,91,94,142|0,30,50,53,57,60,63,67,70,73,'
        '77,80,83,87,90&chco=ff9900,1a00ff&chxt=x,y,x,y&chxl=2:||Duration+in+ms'
        '||3:||%25|&chdl=OpenDNS|UltraDNS'
    )
    self.assertTrue('0,3,27,30,37,43,47,53,57,60,63,67,70,73,77' in expected)
    self.assertTrue('0,0,350|1,0,100' in expected)
    self.assertEquals(url, expected)


if __name__ == '__main__':
  unittest.main()
