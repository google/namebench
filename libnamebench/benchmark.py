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

import random

from . import selectors
from . import util

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

    Returns:
      results: A dictionary of results
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
            for x in range(self.run_count):
              self.results[ns].append([])
          (response, duration, error_msg) = ns.TimedRequest(req_type, record)
          if error_msg:
            duration = ns.timeout
          self.results[ns][test_run].append((record, req_type, duration,
                                             response, error_msg))
    return self.results
