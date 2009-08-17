#!/usr/bin/env python
# Copyright 2009 Google Inc. All Rights Reserved.

"""Simple DNS server comparison benchmarking tool.

Designed to assist system administrators in selection and prioritization.
"""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import csv
import datetime
import math
import operator
import optparse
import random

import charts

VERSION = '1.0b4'

DEFAULT_TIMEOUT = 8

def CalculateListAverage(values):
  """Computes the arithmetic mean of a list of numbers."""
  return sum(values) / float(len(values))


def DrawTextBar(value, max_value, max_width=61.0):
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


def WeightedDistribution(elements, count):
  """Simple exponential distribution with a mean of 10%."""
  max = len(elements) - 1
  desired_mean = max * 0.10
  lambd = 1.0 / desired_mean
  picks = []

  while len(picks) < max:
    index = int(random.expovariate(lambd))
    if index < max:
      picks.append(elements[index])
  return picks


class NameBench(object):
  """The main benchmarking class."""

  def __init__(self, test_domains_path, nameservers={}, run_count=2, test_count=30):
    """Constructor.

    Args:
      test_domains_path: Path to the list of domains to use (str)
      nameservers: a list of NameServerData objects
      run_count: How many test-runs to perform on each nameserver (int)
      test_count: How many DNS lookups to test in each test-run (int)
    """
    self.test_count = test_count
    self.run_count = run_count
    self.nameservers = nameservers
    self.results = {}
    self.domains = self.LoadDomainsList(test_domains_path)

  def LoadDomainsList(self, filename):
    """Read filename with a one-per-line list of domain names."""
    return [line.strip() for line in open(filename).readlines()]

  def GenerateTestRecords(self, domains, count):
    """Generate a set of DNS queries to test with.

    Args:
      domains: a list of domains to base the tests on.
      count: How many tests to create:

    Returns:
      list of tuples in the format of (query type, query_name)
    """
    tests = []
    domains = WeightedDistribution(domains, count)
    random.shuffle(domains)

    # Previously, we used a for loop with random.randomint() to create records,
    # but the types of records generated were too inconsistent.
    for domain in domains[0:int(round(count*0.6))]:
      tests.append(('A', 'www.%s.' % domain))

    for domain in domains[len(tests):len(tests)+int(round(count*0.3))]:
      tests.append(('A', '%s.' % domain))

    # Round rather than truncate this one since it is so small.
    for domain in domains[len(tests):len(tests)+int(round(count*0.05))]:
      tests.append(('MX', '%s.' % domain))

    # We should still have 3-5% left to work with. This means 1 per 30.
    for unused_i in range(len(tests), count):
      tests.append(('A', 'namebench_(RANDOM).com.'))
    return tests

  def BenchmarkNameServer(self, nameserver, tests):
    """Record results for a single run on a nameserver.

    Args:
      nameserver: NameServerData object
      tests: a list of tuples in the form of [(record_type, record_name)]

    Returns:
      results: list of tuples, including data for each request made.
    """
    results = []
    print "   %s" % nameserver
    for (req_type, record) in tests:
      # test records can include a (RANDOM) in the string for cache busting.
      if '(RANDOM)' in record:
        record = record.replace('(RANDOM)', str(random.random() * 10))
      (response, duration, exc) = nameserver.TimedRequest(req_type, record)
      if response:
        answer_count = len(response.answer)
        if answer_count:
          ttl = response.answer[0].ttl
        else:
          ttl = -1
      else:
        answer_count = -1
        ttl = -1

      results.append((record, req_type, duration, answer_count, ttl))
    return results

  def Run(self):
    """Manage all attempts."""
    global_tests = self.GenerateTestRecords(self.domains, self.test_count)
    for attempt in range(self.run_count):
      print('* Benchmarking %s nameservers with %s records each (%s of %s)' %
            (len(self.nameservers), self.test_count, attempt+1, self.run_count))
      for ns in self.nameservers:
        if ns not in self.results:
          self.results[ns] = []

        # TODO(tstromberg): Handle shared caches better!
        # Which is more evil? We want the domains requested
        # to be consistent between nameservers, but we have
        # to beware of cache sharing between IP's. We now
        # drop slower nameservers that share a cache,
        self.results[ns].append(self.BenchmarkNameServer(ns, global_tests))

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

  def NearestNameServer(self):
    min_responses = sorted(self.FastestNameServerResult(),
                           key=operator.itemgetter(1))
    return min_responses[0][0]

  def DisplayResults(self):
    """Display all of the results in an ASCII-graph format."""
    print ''
    print 'Mean Request Duration (in milliseconds):'
    print '-'* 78

    sorted_averages = sorted(self.ComputeAverages(), key=operator.itemgetter(1))

    # Figure out the largest result early on, as we use it to scale the graph.
    max_result = sorted_averages[-1][1]
    for result in sorted_averages:
      (ns, overall_mean, unused_run_means, failure_count) = result
      textbar = DrawTextBar(overall_mean, max_result, max_width=60)
      print '%-13.13s %s %2.0f' % (ns.name, textbar, overall_mean)
      if failure_count:
        print '%-13.13s NOTE: %s had %s timeout(s)' % (ns.name,
                                                       ns.ip, failure_count)
    print ''

    print 'Fastest Response Time for all queries (in milliseconds):'
    print '-'* 78
    min_responses = sorted(self.FastestNameServerResult(),
                           key=operator.itemgetter(1))
    slowest_result = min_responses[-1][1]
    for result in min_responses:
      (ns, duration) = result
      textbar = DrawTextBar(duration, slowest_result, max_width=57)
      print '%-13.13s %s %2.2f' % (ns.name, textbar, duration)
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
    output.writerow(['IP', 'Name', 'Notes', 'Check Duration', 'Test #', 'Record', 'Record Type', 'Duration', 'Answer Count', 'TTL'])
    for ns in self.results:
      for (test_run, test_results) in enumerate(self.results[ns]):
        for result in test_results:
          row = [ns.ip, ns.name, ns.notes, ns.check_duration, test_run]
          row.extend(result)
          output.writerow(row)
    csv_file.close()

