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

"""Some code for  creating Google Chart URI's."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import itertools
import re
import urllib
from graphy.backends import google_chart_api
from graphy import common

CHART_URI = 'http://chart.apis.google.com/chart'

BASE_COLORS = ('ff9900', '1a00ff', '80ff00', 'ff00e6', '00e6ff', 'fae30a',
               '9900ff', '9f5734', '000000', '7b9f34', '3090c0', '477248f',
               'ababab', 'ff0000')

def DarkenHexColorCode(color, shade=1):
  """Given a color in hex format (for HTML), darken it X shades."""
  rgb_values = [int(x, 16) for x in re.findall('\w\w', color)]
  new_color = []
  for value in rgb_values:
    value -= shade*32
    if value <= 0:
      new_color.append('00')
    elif value <= 16:
      # Google Chart API requires that color values be 0-padded.
      new_color.append('0' + hex(value)[2:])
    else:
      new_color.append(hex(value)[2:])

  return ''.join(new_color)


def _GoodTicks(max_value, tick_size=5, num_ticks=10):
  """Find a good round tick size to use in graphs."""
  try_tick = tick_size
  while try_tick < max_value:
    if (max_value / try_tick) > num_ticks:
      try_tick *= 2
    else:
      return try_tick


def PerRunDurationBarGraph(run_data):
  """Output a Google Chart API URL showing per-run durations."""
  chart = google_chart_api.BarChart()
  chart.vertical = False
  chart.bottom.label_gridlines = True
  chart.bottom.label_positions = chart.bottom.labels

  max_run_avg = -1
  runs = {}
  for (ns, run_averages) in run_data:
    chart.left.labels.append(ns)
    for run_num, run_avg in enumerate(run_averages):
      if run_num not in runs:
        runs[run_num] = []

      runs[run_num].append(int(round(run_avg)))
      if run_avg > max_run_avg:
        max_run_avg = run_avg

  for run_num in sorted(runs.keys()):
    chart.AddBars(runs[run_num], label='Run %s' % (run_num+1),
                  color=DarkenHexColorCode('4684ee', run_num*3))

  tick = _GoodTicks(max_run_avg, num_ticks=15)
  labels = range(0, int(round(max_run_avg))+tick, tick)
  chart.bottom.min = 0
  year_axis = chart.AddAxis('x', common.Axis())
  year_axis.labels = ['Duration in ms.']
  year_axis.label_positions = [int((max_run_avg/2.0)*.9)]
  chart.bottom.labels = labels
  chart.bottom.max = labels[-1]
  return chart.display.Url(900, 320)


def _MakeCumulativeDistribution(run_data, x_chunk=0.75, percent_chunk=3):
  """Given run data, generate a cumulative distribution (X in Xms).

  Args:
    run_data: a tuple of nameserver and query durations
    x_chunk: How much value should be chunked together on the x-axis
    percent_chunk: How much percentage should be chunked together on y-axis.

  Returns:
    A list of tuples of tuples: [(ns_name, ((percentage, time),))]

  We chunk the data together to intelligently minimize the number of points
  that need to be passed to the Google Chart API later (URL limitation!)
  """
  # TODO(tstromberg): Use a more efficient algorithm. Pop values out each iter?
  dist = []
  for (ns, results) in run_data:
    host_dist = [(0, 0)]
    max_result = max(results)
    chunk_max = min(results)
    # Why such a low value? To make sure the delta for the first coordinate is
    # always >percent_chunk. We always want to store the first coordinate.
    last_percent = -99

    while chunk_max < max_result:
      values = [x for x in results if x <= chunk_max]
      percent = float(len(values)) / float(len(results)) * 100

      if (percent - last_percent) > percent_chunk:
        host_dist.append((percent, max(values)))
        last_percent = percent

      # TODO(tstromberg): Think about using multipliers to degrade precision.
      chunk_max += x_chunk

    # Make sure the final coordinate is exact.
    host_dist.append((100, max_result))
    dist.append((ns, host_dist))
  return dist


def _MaximumRunDuration(run_data):
  """For a set of run data, return the longest duration.

  Args:
    run_data: a tuple of nameserver and query durations

  Returns:
    longest duration found in runs_data (float)
  """
  times = [x[1] for x in run_data]
  return max(itertools.chain(*times))


def _SortDistribution(a, b):
  """Sort distribution graph by nameserver name."""
  return cmp(a[0].name, b[0].name)


def DistributionLineGraph(run_data, maximum_x=300):
  """Return a Google Chart API URL showing duration distribution per ns."""

  # TODO(tstromberg): Rewrite this method using graphy. Graphy does not
  # support setting explicit x values for line graphs, which makes things
  # difficult.
  distribution = _MakeCumulativeDistribution(run_data)
  datasets = []
  labels = []
  # TODO(tstromberg): Find a way to make colors consistent between runs.
  colors = BASE_COLORS[0:len(distribution)]

  max_value = _MaximumRunDuration(run_data)
  if maximum_x < max_value:
    max_value = maximum_x

  scale = max_value / 100.0

  for (ns, xy_pairs) in sorted(distribution, cmp=_SortDistribution):
    labels.append(urllib.quote_plus(ns.name))
    x = []
    y = []
    for (percentage, duration) in xy_pairs:
      scaled_duration = int(round(duration/scale))
      x.append(scaled_duration)
      y.append(int(round(percentage)))
      # Only append one point passed the scale max.
      if scaled_duration >= 100:
        break

    # TODO(tstromberg): Use google_chart_api.util.EnhancedEncoder
    datasets.append(','.join(map(str, x)))
    datasets.append(','.join(map(str, y)))

  # TODO(tstromberg): See if we can get the % sign in the labels!
  uri = (('%(uri)s?cht=lxy&chs=825x363&chxt=x,y&chg=10,20'
          '&chxr=0,0,%(max)s|1,0,100&chd=t:%(datasets)s&chco=%(colors)s'
          '&chxt=x,y,x,y&chxl=2:||Duration+in+ms||3:||%%25|'
          '&chdl=%(labels)s') %
         {'uri': CHART_URI, 'datasets': '|'.join(map(str, datasets)),
          'max': int(round(max_value)),
          'colors': ','.join(colors), 'labels': '|'.join(labels)})
  return uri
