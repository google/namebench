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
import math
import operator
import random
import sys
import charts
import dns.rcode

def CalculateListAverage(values):
  """Computes the arithmetic mean of a list of numbers."""
  return sum(values) / float(len(values))


def DrawTextBar(value, max_value, max_width=53):
  """Return a simple ASCII bar graph, making sure it fits within max_width.

  Args:
    value: integer or float representing the value of this bar.
    max_value: integer or float representing the largest bar.
    max_width: How many characters this graph can use (int)

  Returns:
    string
  """

  hash_width = max_value / max_width
  return int(math.ceil(value/hash_width)) * '#'


def WeightedDistribution(elements):
  """Simple exponential distribution with a mean of 10%."""
  maximum = len(elements) - 1
  desired_mean = maximum * 0.10
  lambd = 1.0 / desired_mean
  picks = []

  while len(picks) < maximum:
    index = int(random.expovariate(lambd))
    if index < maximum:
      picks.append(elements[index])
  return picks

def ChunkSelect(elements, count):
  start = random.randint(0, len(elements) - count)
  return elements[start:start + count]

class NameBench(object):
  """The main benchmarking class."""

  def __init__(self, nameservers, run_count=2, test_count=30):
    """Constructor.

    Args:
      nameservers: a list of NameServerData objects
      test_domains_path: Path to the list of domains to use (str)
      run_count: How many test-runs to perform on each nameserver (int)
      test_count: How many DNS lookups to test in each test-run (int)
    """
    self.test_count = test_count
    self.run_count = run_count
    self.nameservers = nameservers
    self.results = {}

  def LoadTestData(self, filename, select_mode='weighted'):
    input_data = open(filename).readlines()
    
    if select_mode == 'weighted':
      selected = WeightedDistribution(input_data)[0:self.test_count]
    elif select_mode == 'chunk':
      selected = ChunkSelect(input_data, self.test_count)
    elif select_mode == 'random':
      selected = random.sample(input_data, test_count)
    else:
      raise ValueError('Invalid select_mode: %s' % select_mode)

    self.test_data = []
    for line in selected:
      selection = line.rstrip()
      if ' ' in selection:
        self.test_data.append(selection.split(' ')[0:2])
      else:
        self.test_data.append(('A', self.GenerateFqdn(selection)))
    
    print '- Generated %s tests from %s using %s mode' % (len(self.test_data), filename, select_mode)
    return self.test_data
  
  def GenerateFqdn(self, domain):
    oracle = random.randint(0, 100)
    if oracle < 70:
      return 'www.%s.' % domain
    elif oracle < 97:
      return '%s.' % domain
    else:
      return 'cache-%s.%s.' % (random.randint(0,10000), domain)

  def BenchmarkNameServer(self, nameserver, tests):
    """Record results for a single run on a nameserver.

    Args:
      nameserver: NameServerData object
      tests: a list of tuples in the form of [(record_type, record_name)]

    Returns:
      results: list of tuples, including data for each request made.
    """
    results = []
    for (req_type, record) in tests:
      # test records can include a (RANDOM) in the string for cache busting.
      if '(RANDOM)' in record:
        record = record.replace('(RANDOM)', str(random.random() * 10))
      (response, duration) = nameserver.TimedRequest(req_type, record)[0:2]
      results.append((record, req_type, duration, response))
    return results

  def Run(self):
    """Manage all attempts."""
    for attempt in range(self.run_count):
      sys.stdout.write('* Benchmarking %s nameservers with %s records each (%s of %s).' %
                       (len(self.nameservers), self.test_count, attempt+1, self.run_count))
      for ns in self.nameservers:
        if ns not in self.results:
          self.results[ns] = []
        sys.stdout.write('.')
        sys.stdout.flush()
        self.results[ns].append(self.BenchmarkNameServer(ns, self.test_data))
      sys.stdout.write('\n')
    sys.stdout.flush()

  def ComputeAverages(self):
    """Process all runs for all hosts, yielding an average for each host."""
    for ns in self.results:
      record_count = 0
      failure_count = 0
      run_averages = []

      for test_run in self.results[ns]:
        record_count += len(test_run)
        failure_count += len([x[3] for x in test_run if x[3] == -1])
        duration = sum([x[2] for x in test_run])
        run_averages.append(duration / len(test_run))

      # This appears to be a safe use of averaging averages
      overall_average = CalculateListAverage(run_averages)
      yield (ns, overall_average, run_averages, failure_count)

  def FastestNameServerResult(self):
    """Process all runs for all hosts, yielding an average for each host."""
    return [(x[0], min(x[1])) for x in self.DigestedResults()]

  def BestOverallNameServer(self):
    sorted_averages = sorted(self.ComputeAverages(), key=operator.itemgetter(1))
    return sorted_averages[0][0]

  def NearestNameServers(self, count=2):
    min_responses = sorted(self.FastestNameServerResult(),
                           key=operator.itemgetter(1))
    return [x[0] for x in min_responses][0:count]

  def DisplayResults(self):
    """Display all of the results in an ASCII-graph format."""

    print ''
    print 'Lowest latency for an individual query (in milliseconds):'
    print '-'* 78
    min_responses = sorted(self.FastestNameServerResult(),
                           key=operator.itemgetter(1))
    slowest_result = min_responses[-1][1]
    for result in min_responses:
      (ns, duration) = result
      textbar = DrawTextBar(duration, slowest_result)
      print '%-16.16s %s %2.2f' % (ns.name, textbar, duration)
    

    print ''
    print 'Overall Mean Request Duration (in milliseconds):'
    print '-'* 78    
    sorted_averages = sorted(self.ComputeAverages(), key=operator.itemgetter(1))
    max_result = sorted_averages[-1][1]
    timeout_seen = False
    for result in sorted_averages:
      (ns, overall_mean, unused_run_means, failure_count) = result
      if failure_count:
        timeout_seen = True
        note = ' (%sT)' % failure_count
      else:
        note = ''
      textbar = DrawTextBar(overall_mean, max_result)
      print '%-16.16s %s %2.0f%s' % (ns.name, textbar, overall_mean, note)
    if timeout_seen:
      print '* (#T) represents the number of timeouts experienced during testing.'
    print ''
    

    print 'Detailed Mean Request Duration Chart URL'
    print '-' * 78
    runs_data = [(x[0].name, x[2]) for x in sorted_averages]
    print charts.PerRunDurationBarGraph(runs_data)
    print ''
    print 'Detailed Request Duration Distribution Chart URL'
    print '-' * 78
    print charts.DistributionLineGraph(self.DigestedResults())

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
    csv_file = open(filename, 'w')
    output = csv.writer(csv_file)
    output.writerow(['IP', 'Name', 'Check Duration', 'Test #', 'Record', 'Record Type', 'Duration', 'TTL', 'Answer Count', 'Response'])
    for ns in self.results:
      for (test_run, test_results) in enumerate(self.results[ns]):
        for (record, req_type, duration, response) in test_results:
          answer_text = ''
          answer_count = -1
          ttl = -1
          if response:
            if response.answer:
              answer_count = len(response.answer)
              answers = [' + '.join(map(str, x.items)) for x in response.answer]
              answer_text = ' -> '.join(answers)
              ttl = response.answer[0].ttl
            else:
              answer_text = dns.rcode.to_text(response.rcode())
          output.writerow([ns.ip, ns.name, ns.check_duration, test_run, record, req_type, duration, ttl, answer_count, answer_text])
          
    csv_file.close()

