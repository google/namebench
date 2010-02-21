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
    self.status_callback = status_callback

  def msg(self, msg, **kwargs):
    if self.status_callback:
      self.status_callback(msg, **kwargs)

  def SelectTestRecords(self, input_data, select_mode='weighted'):
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
      return selectors.WeightedDistribution(input_data, self.test_count)
    elif select_mode == 'chunk':
      return selectors.ChunkSelect(input_data, self.test_count)
    elif select_mode == 'random':
      return selectors.RandomSelect(input_data, self.test_count)
    else:
      raise ValueError('Invalid select_mode: %s' % select_mode)

  def Run(self, test_records=None):
    """Manage and execute all tests on all nameservers.

    We used to run all tests for a nameserver, but the results proved to be
    unfair if the bandwidth was suddenly constrained. We now run a test on
    each server before moving on to the next.

    Returns:
      results: A dictionary of results
    """
    test_data = self.SelectTestRecords(test_records)
    for test_run in range(self.run_count):
      state = ('Benchmarking %s server(s), run %s of %s' %
               (len(self.nameservers.enabled), test_run+1, self.run_count))
      count = 0
      for (request_type, hostname) in test_data:
        count += 1
        self.msg(state, count=count, total=len(test_data))
        for ns in self.nameservers.enabled:
          if ns not in self.results:
            self.results[ns] = []
            for x in range(self.run_count):
              self.results[ns].append([])
          (response, duration, error_msg) = ns.TimedRequest(request_type, hostname)
          if error_msg:
            duration = ns.timeout
          self.results[ns][test_run].append((hostname, request_type, duration,
                                             response, error_msg))
    return self.results
