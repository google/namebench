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


"""Simple DNS server comparison benchmarking tool.

Designed to assist system administrators in selection and prioritization.
"""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import csv
import datetime
import operator
import os.path
import random
import sys
import math

# external dependencies (from third_party)
try:
  import third_party
except ImportError:
  pass

import jinja2

import charts
import selectors
import util



class Benchmark(object):
  """The main benchmarking class."""

  def __init__(self, nameservers, run_count=2, test_count=30,
               status_callback=None):
    """Constructor.

    Args:
      nameservers: a list of NameServerData objects
      run_count: How many test-runs to perform on each nameserver (int)
      test_count: How many DNS lookups to test in each test-run (int)
    """
    self.test_count = test_count
    self.run_count = run_count
    self.nameservers = nameservers
    self.results = {}
    self.test_data = []
    self.status_callback = status_callback

  def msg(self, msg, **kwargs):
    if self.status_callback:
      self.status_callback(msg, **kwargs)
    else:
      print '%s [%s/%s]' % (msg, count, total)

  def CreateTestsFromFile(self, filename, select_mode='weighted'):
    """Open an input file, and pass the data to CreateTests."""
    filename = util.FindDataFile(filename)
    self.msg('Reading test data from %s' % filename)
    input_data = open(filename).readlines()
    return self.CreateTests(input_data, select_mode=select_mode)

  def CreateTests(self, input_data, select_mode='weighted'):
    """Load test input data input, and create tests from it.

    Args:
      input_data: a list of hostnames to benchmark against.
      select_mode: how to randomly select which hostnames to use. Valid modes:
                   weighted, random, chunk

    Returns:
      A list of tuples containing record_type (str) and hostname (str)

    Raises:
      ValueError: If select_mode is incorrect.
    """
    if select_mode == 'weighted' and len(input_data) != len(set(input_data)):
      print '* input contains duplicates, switching select_mode to random'
      select_mode = 'random'
    if select_mode == 'weighted':
      selected = selectors.WeightedDistribution(input_data, self.test_count)
    elif select_mode == 'chunk':
      selected = selectors.ChunkSelect(input_data, self.test_count)
    elif select_mode == 'random':
      selected = selectors.RandomSelect(input_data, self.test_count)
    else:
      raise ValueError('Invalid select_mode: %s' % select_mode)

    self.test_data = []
    for line in selected:
      selection = line.rstrip()
      if len(selection) < 2:
        continue

      if ' ' in selection:
        self.test_data.append(selection.split(' ')[0:2])
      else:
        self.test_data.append(('A', self.GenerateFqdn(selection)))

    assert self.test_data
    return self.test_data

  def GenerateFqdn(self, domain):
    oracle = random.randint(0, 100)
    if oracle < 60:
      return 'www.%s.' % domain
    elif oracle < 95:
      return '%s.' % domain
    elif oracle < 98:
      return 'static.%s.' % domain
    else:
      return 'cache-%s.%s.' % (random.randint(0, 10), domain)

  def Run(self):
    """Manage and execute all tests on all nameservers.

    We used to run all tests for a nameserver, but the results proved to be
    unfair if the bandwidth was suddenly constrained. We now run a test on
    each server before moving on to the next.
    """
    assert self.test_data
    for test_run in range(self.run_count):
      state = ('Benchmarking %s server(s), run %s of %s' %
               (len(self.nameservers.enabled), test_run+1, self.run_count))
      count = 0
      for (req_type, record) in self.test_data:
        count += 1
        self.msg(state, count=count, total=len(self.test_data))
        for ns in self.nameservers.enabled:
          if ns not in self.results:
            self.results[ns] = []
            for run_num in range(self.run_count):
              self.results[ns].append([])
          (response, duration, exc) = ns.TimedRequest(req_type, record)
          if exc:
            duration = ns.timeout
          self.results[ns][test_run].append((record, req_type, duration,
                                             response))

  def ComputeAverages(self):
    """Process all runs for all hosts, yielding an average for each host."""
    for ns in self.results:
      record_count = 0
      failure_count = 0
      nx_count = 0
      run_averages = []

      for test_run in self.results[ns]:
        record_count += len(test_run)
        # x: record, req_type, duration, response
        failure_count += len([x for x in test_run if not x[3]])
        nx_count += len([x for x in test_run if x[3] and not x[3].answer])
        duration = sum([x[2] for x in test_run])        
        run_averages.append(duration / len(test_run))

      # This appears to be a safe use of averaging averages
      overall_average = util.CalculateListAverage(run_averages)
      (fastest, slowest) = self.FastestAndSlowestDurationForNameServer(ns)
      
      yield (ns, overall_average, run_averages, fastest, slowest,
             failure_count, nx_count)

  def FastestAndSlowestDurationForNameServer(self, ns):
    """For a given nameserver, find the fastest/slowest non-error durations."""
  
    fastest_duration = 2**32
    slowest_duration = -1
    for test_run_results in self.results[ns]:
      for (host, type, duration, response) in test_run_results:
        if response and response.answer:
          if duration < fastest_duration:
            fastest_duration = duration
        if duration > slowest_duration:
          slowest_duration = duration        
    return (fastest_duration, slowest_duration)

  def FastestNameServerResult(self):
    """Process all runs for all hosts, yielding an average for each host."""
    # TODO(tstromberg): This should not count queries which failed.
    fastest = [(ns, self.FastestAndSlowestDurationForNameServer(ns)[0]) for ns in self.results] 
    return sorted(fastest, key=operator.itemgetter(1))

  def BestOverallNameServer(self):
    sorted_averages = sorted(self.ComputeAverages(), key=operator.itemgetter(1))
    hosts = [ x[0] for x in sorted_averages ]
    for host in [ x[0] for x in sorted_averages ]:
      if not host.is_error_prone:
        return host
    # return something if none of them are good.
    return hosts[0]

  def NearestNameServers(self, count=2):
    min_responses = sorted(self.FastestNameServerResult(),
                           key=operator.itemgetter(1))
    return [x[0] for x in min_responses][0:count]

  def _LowestLatencyAsciiChart(self):
    """Return a simple set of tuples to generate an ASCII chart from."""
    fastest = self.FastestNameServerResult()
    slowest_result = fastest[-1][1]
    chart = []
    for (ns, duration) in fastest:
      textbar = util.DrawTextBar(duration, slowest_result)
      chart.append((ns.name, textbar, duration))
    return chart

  def _MeanRequestAsciiChart(self):
    sorted_averages = sorted(self.ComputeAverages(), key=operator.itemgetter(1))
    max_result = sorted_averages[-1][1]
    chart = []
    for result in sorted_averages:
      (ns, overall_mean) = result[0:2]
      textbar = util.DrawTextBar(overall_mean, max_result)
      chart.append((ns.name, textbar, overall_mean))
    return chart

  def CreateReport(self, format='ascii', config=None, output_fp=None,
                   csv_path=None):
    lowest_latency = self._LowestLatencyAsciiChart()
    mean_duration = self._MeanRequestAsciiChart()
    sorted_averages = sorted(self.ComputeAverages(), key=operator.itemgetter(1))
    # This was used to enforce consistent scaling between min/mean graphs.
    duration_scale = math.ceil(max(sorted_averages[-1][2]))

    runs_data = [(x[0].name, x[2]) for x in sorted_averages]
    mean_duration_url = charts.PerRunDurationBarGraph(runs_data)
    min_duration_url = charts.MinimumDurationBarGraph(self.FastestNameServerResult())
    distribution_url_200 = charts.DistributionLineGraph(self.DigestedResults(),
                                                        scale=200)
    distribution_url = charts.DistributionLineGraph(self.DigestedResults())
    best = self.BestOverallNameServer()
    nearest = [x for x in self.NearestNameServers(3) if x.ip != best.ip][0:2]
    recommended = [best] + nearest

    nameserver_details = list(sorted_averages)
    for ns in self.nameservers:
      if ns.disabled:
        nameserver_details.append((ns, 0.0, [], 0, 0, 0))

    builtin_servers = util.InternalNameServers()
    system_primary = builtin_servers[0]
    other_records = [ x for x in nameserver_details if x[0] != best and not x[0].disabled and not x[0].is_error_prone ]

    if other_records:
      # First try to compare against our primary DNS
      comparison_record = [x for x in other_records if x[0].system_position == 0]
      # Then the fastest "primary"
      if not comparison_record:
        comparison_record = [x for x in other_records if x[0].is_primary]
      # Fall back to the second fastest of any type.
      if not comparison_record:
        comparison_record = other_records
      comparison = {
        'percent': ((comparison_record[0][1] / nameserver_details[0][1])-1) * 100,
        'ns': comparison_record[0][0]
      }
    else:
      comparison = {
        'percent': 0,
        'ns': nameserver_details[0][0]
      }
    
    # Fragile, makes assumption about the CSV being in the same path as the HTML file
    if csv_path:
      csv_link = os.path.basename(csv_path)
    else:
      csv_link = None

    template_name = '%s.tmpl' % format
    template_path = util.FindDataFile(os.path.join('templates', template_name))
    filtered_config = self.FilteredConfig(config)
    template_dir = os.path.dirname(template_path)
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))
    template = env.get_template(template_name)
    self.msg('Rendering template: %s' % template_name)
    rendered = template.render(
        system_primary=system_primary,
        timestamp = datetime.datetime.now(),
        lowest_latency=lowest_latency,
        best=best,
        comparison=comparison,
        config=filtered_config,
        mean_duration=mean_duration,
        nameserver_details=nameserver_details,
        mean_duration_url=mean_duration_url,
        min_duration_url=min_duration_url,
        distribution_url=distribution_url,
        distribution_url_200=distribution_url_200,
        recommended=recommended,
        csv_link=csv_link
    )
    self.msg('Saving rendered %s output' % format)
    if output_fp:
      output_fp.write(rendered)
    else:
      return rendered

  def FilteredConfig(self, config):
    """Generate a watered down config listing for our report."""
    keys = [x for x in dir(config) if not x.startswith('_') and x != 'config' ]
    config_items = []
    for key in keys:
      value = getattr(config, key)
      # > values are ConfigParser internals. None values are just noise.
      if isinstance(value, int) or isinstance(value, float) or isinstance(value, str):
        config_items.append((key, value))
    return sorted(config_items)

  def DigestedResults(self):
    """Return a tuple of nameserver and all associated durations."""
    duration_data = []
    for ns in self.results:
      durations = []
      for test_run_results in self.results[ns]:
        durations += [x[2] for x in test_run_results]
      duration_data.append((ns, durations))
    return duration_data

  def SaveResultsToCsv(self, filename):
    """Write out a CSV file with detailed results on each request.

    Args:
      filename: full path on where to save results (string)

    Sample output:
    nameserver, test_number, test, type, duration, answer_count, ttl
    """
    self.msg("Opening %s for write" % filename, debug=Tre)
    csv_file = open(filename, 'w')
    output = csv.writer(csv_file)
    output.writerow(['IP', 'Name', 'Check Duration', 'Test #', 'Record',
                     'Record Type', 'Duration', 'TTL', 'Answer Count',
                     'Response'])
    for ns in self.results:
      self.msg("Saving detailed data for %s" % ns, debug=True)
      for (test_run, test_results) in enumerate(self.results[ns]):
        for (record, req_type, duration, response) in test_results:
          answer_text = ''
          answer_count = -1
          ttl = -1
          if response:
            if response.answer:
              answer_count = len(response.answer)
              ttl = response.answer[0].ttl
            answer_text = ns.ResponseToAscii(response)
          output.writerow([ns.ip, ns.name, ns.check_duration, test_run, record,
                           req_type, duration, ttl, answer_count, answer_text])
    csv_file.close()
    self.msg("%s saved." % filename, debug=True)

