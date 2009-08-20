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
import charts


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
    self.assertTrue('s%3AFN6%2CDNN' in results)

    expected = (
        'http://chart.apis.google.com/chart?chxt=y%2Cx&'
        'chd=s%3AFN6%2CDNN&chxr=1%2C-0.6%2C75&chxtc=1%2C-900'
        '&chco=4684ee%2C00248e&chbh=a&chp=0.00793650793651&chs=900x320'
        '&cht=bhg&chxl=0%3A%7C172.168.1.2%7C192.168.1.2%7C10.0.0.1%7C1%3A%7C0'
        '%7C5%7C10%7C15%7C20%7C25%7C30%7C35%7C40%7C45%7C50%7C55%7C60%7C65%7C70'
        '%7C75&chdl=Run%201%7CRun%202'
    )
    self.assertEqual(results, expected)

  def testMaximumRunDuration(self):
    runs_data = [
        ('G', [3.851, 4.7690, 423.971998, 189.674001, 14.477, 174.788001]),
        ('Y', [99.99, 488.88])
    ]
    self.assertEquals(charts._MaximumRunDuration(runs_data), 488.88)

  def testSimpleCumulativeDistribution(self):
    runs_data = [
        ('UDS', [13.323, 23.919, 17.27799, 13.794, 13.199, 12.8670001, 13.231,
                 12.968, 13.241, 15.9990001, 13.24, 62.3340003, 13.4730001,
                 13.805, 13.269, 12.93399, 13.2070001, 13.24499, 13.384,
                 15.2650001]),
        ('G', [2.3260, 14.0020001, 486.690997, 3.2250, 9.571992, 2.029998,
               288.221, 2.4820, 2.3380, 114.94, 2.21, 2.2080, 2.2050, 2.161999,
               1.544, 1.244, 1.335, 1.637999, 2.1150, 2.133999])]
    expected = [('UDS', [(0, 0), (5.0, 12.8670001), (65.0, 13.4730001),
                         (75.0, 13.805), (80.0, 15.2650001),
                         (85.0, 15.9990001), (90.0, 17.277989999999999),
                         (95.0, 23.919), (100, 62.3340003)]),
                ('G', [(0, 0), (5.0, 1.244), (20.0, 1.637999),
                       (70.0, 2.4820000000000002), (75.0, 3.2250000000000001),
                       (80.0, 9.5719919999999998), (85.0, 14.0020001),
                       (90.0, 114.94), (95.0, 288.221),
                       (100, 486.69099699999998)])]
    self.assertEqual(charts._MakeCumulativeDistribution(runs_data), expected)
    expected = ('http://chart.apis.google.com/chart?cht=lxy&chs=1000x300'
                '&chxt=x,y&chg=10,20&chxr=0,0,62|1,0,100&chd=t:0,21,22,22,24,'
                '26,28,38,100|0,5,65,75,80,85,90,95,100&chco=ff9900&chdl=UDS')
    self.assertEqual(charts.DistributionLineGraph([runs_data[0]]), expected)

    expected = ('http://chart.apis.google.com/chart?cht=lxy&chs=1000x300&'
                'chxt=x,y&chg=10,20&chxr=0,0,200|1,0,100&chd=t:0,1,1,1,2,5,7,'
                '57,144|0,5,20,70,75,80,85,90,95&chco=ff9900&chdl=G')
    self.assertEqual(charts.DistributionLineGraph([runs_data[1]]), expected)

  def testSimpleCumulativeDistribution2(self):
    runs_data = [
        ('G', [3.851, 4.7690, 423.971998, 189.674001, 14.477, 174.788001,
               309.694999, 313.672003, 12.1750001, 113.922, 2.0640, 2.8330,
               1.982, 2.8399, 2.173, 1.7330, 2.222999, 1.6910, 2.238, 2.165])
    ]
    expected = [('G', [(0, 0), (5.0, 1.6910000000000001), (40.0, 2.238),
                       (50.0, 2.8399000000000001), (55.000000000000007, 3.851),
                       (60.0, 4.7690000000000001), (65.0, 12.1750001),
                       (70.0, 14.477), (75.0, 113.922),
                       (80.0, 174.78800100000001), (85.0, 189.674001),
                       (90.0, 309.694999), (95.0, 313.67200300000002),
                       (100, 423.97199799999999)])]
    self.assertEqual(charts._MakeCumulativeDistribution(runs_data), expected)

    expected = ('http://chart.apis.google.com/chart?cht=lxy&chs=1000x300&'
                'chxt=x,y&chg=10,20&chxr=0,0,200|1,0,100&chd=t:0,1,1,1,2,2,6,'
                '7,57,87,95,155|0,5,40,50,55,60,65,70,75,80,85,90&chco=ff9900'
                '&chdl=G')
    self.assertEqual(charts.DistributionLineGraph([runs_data[0]]), expected)

  def testSimpleCumulativeDistributionLarger(self):
    runs_data = [
        ('UDS', [12.279, 18.186, 15.493, 12.57499, 12.67099, 11.664, 12.019,
                 12.09, 12.185, 20.7330001, 12.09, 275.589997, 20.4229998,
                 11.798, 12.6080001, 15.606, 350.492002, 160.638001,
                 161.384999, 11.8260001, 12.32799, 151.251, 12.196,
                 87.5529997, 90.9590003, 12.148, 184.019001, 87.1449996,
                 20.6350002, 14.15499, 12.1170001, 12.9760001, 12.238,
                 12.551, 12.009, 11.728, 11.987, 11.82499, 12.073, 13.834,
                 11.972, 11.89199, 12.074, 11.79599, 12.583, 15.228,
                 11.7490001, 12.278, 12.541, 11.82, 12.269, 12.129, 12.13599,
                 11.81, 11.85699, 12.145, 11.968, 11.8770001, 19.50499,
                 13.8190001]),
        ('G', [2.222, 2.6640, 148.089, 2.367, 2.311998, 2.0430, 2.3420, 1.24,
               2.259998, 130.369, 324.050001, 256.6399, 4.283998, 305.178997,
               2.536, 1219.51, 327.673998, 157.75, 174.681001, 162.9199,
               166.5099, 290.793998, 2.363999, 295.968999, 163.930001, 1.891,
               1.9370, 14.853, 14.371, 21.634, 2.1080, 2.29, 2.3450, 2.758,
               2.181999, 1.6140, 1.7190, 2.061998, 1.976, 2.145, 1.6890,
               1.756999, 1.8080, 1.935999, 2.5899, 4.0510, 1.665999, 1.9850,
               2.1200, 1.595, 1.9299, 1.7310, 1.286999, 1.764999, 1.792,
               1.296, 1.871, 1.816999, 14.53999, 8.423])
    ]

    expected = [
        ('UDS', [(0, 0), (1.6666666666666667, 11.664),
                 (55.000000000000007, 12.32799),
                 (66.666666666666657, 12.9760001),
                 (70.0, 13.834),
                 (73.333333333333329, 15.228),
                 (76.666666666666671, 15.606),
                 (80.0, 19.504989999999999),
                 (83.333333333333343, 20.6350002),
                 (86.666666666666671, 87.144999600000006),
                 (90.0, 90.9590003), (93.333333333333329, 160.638001),
                 (96.666666666666671, 184.019001),
                 (100, 350.49200200000001)]),
        ('G', [(0, 0), (1.6666666666666667, 1.24), (35.0, 1.9850000000000001),
               (63.333333333333329, 2.6640000000000001),
               (66.666666666666657, 4.0510000000000002), (70.0, 8.423),
               (73.333333333333329, 14.53999),
               (76.666666666666671, 21.634), (80.0, 148.089),
               (83.333333333333343, 162.91990000000001),
               (86.666666666666671, 166.50989999999999),
               (90.0, 256.63990000000001), (93.333333333333329, 295.968999),
               (96.666666666666671, 324.05000100000001), (100, 1219.51)])
    ]
    self.assertEqual(charts._MakeCumulativeDistribution(runs_data), expected)


class VisualChartTests(unittest.TestCase):
  """These tests are meant for visual comparison (by hand)."""

  def testCumulativeDistributionGO(self):
    runs_data = [
        ('ODS-2', [86.594, 86.9050, 86.73004, 87.1400, 86.68698, 86.45198,
                   86.683007, 86.47299, 86.57593, 86.808007, 81.117004,
                   81.31002, 81.063002, 81.48395, 81.075003, 80.79006,
                   81.141005, 80.878, 80.869, 81.20093]),
        ('G', [2.492, 2.172002, 2.44700, 2.11200, 1.599, 1.694, 2.31400,
               1.21300, 1.2549, 2.2789, 2.442002, 1.84800, 2.4969,
               3.2869, 1.32800, 1.11400, 1.95500, 1.21900, 1.2689, 2.115002]),
    ]
    expected = ('http://chart.apis.google.com/chart?cht=lxy&chs=1000x300&'
                'chxt=x,y&chg=10,20&chxr=0,0,87|1,0,100&chd=t:0,1,2,3,4|'
                '0,5,45,95,100|0,93,94,100|0,5,50,85&chco=ff9900,3dbecc'
                '&chdl=G|ODS-2')
    self.assertEqual(charts.DistributionLineGraph(runs_data), expected)

  def testCumulativeDistribution(self):
    runs_data = [
        ('UDS', [12.202, 13.256, 12.715, 13.122, 12.375, 12.2070, 12.7639,
                 12.052, 12.2490, 104.638, 13.224, 14.116, 13.365, 13.7349,
                 13.371, 12.792, 13.1560, 12.778, 13.0500, 114.114]),
        ('ODS-2', [86.594, 86.9050, 86.73004, 87.1400, 86.68698, 86.45198,
                   86.683007, 86.47299, 86.57593, 86.808007, 81.117004,
                   81.31002, 81.063002, 81.48395, 81.075003, 80.79006,
                   81.141005, 80.878, 80.869, 81.20093]),
        ('Scarlet', [10.539, 10.8580, 10.3130, 10.8640, 10.35399, 10.09,
                     0.4250, 10.331, 10.6010, 10.609, 10.913, 10.7260, 11.1170,
                     11.0, 10.68099, 10.9890, 11.2010, 11.023, 10.8580,
                     10.695]),
        ('G', [2.492, 2.172002, 2.44700, 2.11200, 1.599, 1.694, 2.31400,
               1.21300, 1.2549, 2.2789, 2.442002, 1.84800, 2.4969,
               3.2869, 1.32800, 1.11400, 1.95500, 1.21900, 1.2689, 2.115002]),
        ('Scarlet-2', [10.0020, 10.289, 10.115, 9.965993, 9.954006, 9.817002,
                       9.916998, 10.234, 9.9297, 10.15199, 9.458002, 9.308993,
                       9.4359, 9.557998, 9.490002, 9.503996, 9.430992,
                       9.349002, 9.525998, 9.441007]),
        ('ODS', [87.14796, 87.555007, 87.33194, 87.70994, 87.094, 86.93998,
                 87.182002, 86.97794, 87.173002, 87.34499, 84.52296,
                 84.81002, 84.894005, 84.906006, 84.58899, 84.423002,
                 84.489004, 84.287006, 84.49295, 84.697003]),
        ('10.10.224.68', [14994.374, 20.128, 14.83799, 214.602, 353.108,
                          513.7359, 735.890996, 566.27302, 18.445, 277.6949,
                          14.26699, 13.6170, 13.85, 14.24799, 12.67399,
                          17.045002, 12.664, 12.263, 12.702, 13.9920])
    ]
    expected = ('http://chart.apis.google.com/chart?cht=lxy&chs=1000x300'
                '&chxt=x,y&chg=10,20&chxr=0,0,200|1,0,100&chd=t:0,1,1,1,2|'
                '0,5,45,95,100|0,5,5,5|0,5,80,100|0,0,5,5,6|0,5,10,75,100|'
                '0,40,41,43,44|0,5,50,85,100|0,42,42,44,44|0,5,50,80,100|'
                '0,6,6,7,7,52,57|0,5,45,80,90,95,100|0,6,6,7,7,7,9,9,10,107|'
                '0,5,20,25,45,50,55,60,65,70&chco=ff9900,3dbecc,ff3912,303030,'
                '4684ee,fae30a,cc3ebd&chdl=G|Scarlet-2|Scarlet|ODS-2|ODS|UDS|'
                '10.10.224.68')
    self.assertEqual(charts.DistributionLineGraph(runs_data), expected)

if __name__ == '__main__':
  unittest.main()
