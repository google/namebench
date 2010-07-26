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
import math
import re
import urllib

# external dependencies (from nb_third_party)
from graphy import common
from graphy.backends import google_chart_api

CHART_URI = 'http://chart.apis.google.com/chart'
BASE_COLORS = ('ff9900', '1a00ff', 'ff00e6', '80ff00', '00e6ff', 'fae30a',
               'BE81F7', '9f5734', '000000', 'ff0000', '3090c0', '477248f',
               'ababab', '7b9f34', '00ff00', '0000ff', '9900ff', '405090',
               '051290', 'f3e000', '9030f0', 'f03060', 'e0a030', '4598cd')
CHART_WIDTH = 720
CHART_HEIGHT = 415


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


def _GoodTicks(max_value, tick_size=2.5, num_ticks=10.0):
  """Find a good round tick size to use in graphs."""
  try_tick = tick_size
  while try_tick < max_value:
    if (max_value / try_tick) > num_ticks:
      try_tick *= 2
    else:
      return int(round(try_tick))
  # Fallback
  print "Could not find good tick size for %s (size=%s, num=%s)" % (max_value, tick_size, num_ticks)
  simple_value = int(max_value  / num_ticks)
  if simple_value > 0:
    return simple_value
  else:
    return 1

def _BarGraphHeight(bar_count):
  # TODO(tstromberg): Fix hardcoding.
  proposed_height = 52 + (bar_count*13)
  if proposed_height > CHART_HEIGHT:
    return CHART_HEIGHT
  else:
    return proposed_height


def PerRunDurationBarGraph(run_data, scale=None):
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

      runs[run_num].append(run_avg)
      if run_avg > max_run_avg:
        max_run_avg = run_avg

  if max_run_avg < 0:
    print "No decent data to graph: %s" % run_data
    return None

  if not scale:
    scale = int(math.ceil(max_run_avg / 5) * 5)

  if len(runs) == 1:
    bar_count = len(runs[0])
    chart.AddBars(runs[0])
  else:
    bar_count = 0
    for run_num in sorted(runs):
      bar_count += len(runs[run_num])
      chart.AddBars(runs[run_num], label='Run %s' % (run_num+1),
                    color=DarkenHexColorCode('4684ee', run_num*3))

  tick = _GoodTicks(scale, num_ticks=15.0)
  labels = range(0, scale, tick) + [scale]
  chart.bottom.min = 0
  chart.display.enhanced_encoding = True
  bottom_axis = chart.AddAxis('x', common.Axis())
  bottom_axis.labels = ['Duration in ms.']
  bottom_axis.label_positions = [int((max_run_avg/2.0)*.9)]
  chart.bottom.labels = labels
  chart.bottom.max = labels[-1]
  return chart.display.Url(CHART_WIDTH, _BarGraphHeight(bar_count))


def MinimumDurationBarGraph(fastest_data, scale=None):
  """Output a Google Chart API URL showing minimum-run durations."""
  chart = google_chart_api.BarChart()
  chart.vertical = False
  chart.bottom.label_gridlines = True
  chart.bottom.label_positions = chart.bottom.labels
  chart.AddBars([x[1] for x in fastest_data])
  chart.left.labels = [x[0].name for x in fastest_data]

  slowest_time = fastest_data[-1][1]
  if not scale:
    scale = int(math.ceil(slowest_time / 5) * 5)

  tick = _GoodTicks(scale, num_ticks=15.0)
  labels = range(0, scale, tick) + [scale]
  chart.bottom.min = 0
  chart.bottom.max = scale
  chart.display.enhanced_encoding = True
  bottom_axis = chart.AddAxis('x', common.Axis())
  bottom_axis.labels = ['Duration in ms.']
  bottom_axis.label_positions = [int((scale/2.0)*.9)]
  chart.bottom.labels = labels
  return chart.display.Url(CHART_WIDTH, _BarGraphHeight(len(chart.left.labels)))


def _MakeCumulativeDistribution(run_data, x_chunk=1.5, percent_chunk=3.5):
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
    if not results:
      continue
    
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
  sys_pos_cmp = cmp(b[0].system_position, a[0].system_position)
  if sys_pos_cmp:
    return sys_pos_cmp

  preferred_cmp = cmp(b[0].is_keeper, a[0].is_keeper)
  if preferred_cmp:
    return preferred_cmp

  return cmp(a[0].name, b[0].name)


def DistributionLineGraph(run_data, scale=None, sort_by=None):
  """Return a Google Chart API URL showing duration distribution per ns."""

  # TODO(tstromberg): Rewrite this method using graphy. Graphy does not
  # support setting explicit x values for line graphs, which makes things
  # difficult.
  distribution = _MakeCumulativeDistribution(run_data)
  datasets = []
  labels = []
  # TODO(tstromberg): Find a way to make colors consistent between runs.
  colors = BASE_COLORS[0:len(distribution)]

  if not sort_by:
    sort_by = _SortDistribution

  max_value = _MaximumRunDuration(run_data)
  if not scale:
    scale = max_value
  elif scale < max_value:
    max_value = scale

  scale = max_value / 100.0

  for (ns, xy_pairs) in sorted(distribution, cmp=sort_by):
    if len(ns.name) > 1:
      labels.append(urllib.quote_plus(ns.name))
    else:
      labels.append(urllib.quote_plus(ns.ip))
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
  uri = (('%(uri)s?cht=lxy&chs=%(x)sx%(y)s&chxt=x,y&chg=10,20'
          '&chxr=0,0,%(max)s|1,0,100&chd=t:%(datasets)s&chco=%(colors)s'
          '&chxt=x,y,x,y&chxl=2:||Duration+in+ms||3:||%%25|'
          '&chdl=%(labels)s') %
         {'uri': CHART_URI, 'datasets': '|'.join(map(str, datasets)),
          'max': int(round(max_value)), 'x': CHART_WIDTH, 'y': CHART_HEIGHT,
          'colors': ','.join(colors), 'labels': '|'.join(labels)})
  return uri
