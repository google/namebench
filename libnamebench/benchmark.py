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
import threading
import time
import Queue

from . import selectors
from . import util

class BenchmarkThreads(threading.Thread):
  """Benchmark multiple nameservers in parallel."""
  def __init__(self, input_queue, results_queue):
    threading.Thread.__init__(self)
    self.input = input_queue
    self.results = results_queue

  def run(self):
    """Iterate over the queue, processing each item."""
    while not self.input.empty():
      try:
        (ns, request_type, hostname) = self.input.get_nowait()
        (response, duration, error_msg) = ns.TimedRequest(request_type, hostname)
        self.results.put((ns, request_type, hostname, response, duration, error_msg))
      except Queue.Empty:
        return

class Benchmark(object):
  """The main benchmarking class."""

  def __init__(self, nameservers, run_count=2, test_count=30, thread_count=1,
               status_callback=None):
    """Constructor.

    Args:
      nameservers: a list of NameServerData objects
      run_count: How many test-runs to perform on each nameserver (int)
      test_count: How many DNS lookups to test in each test-run (int)
    """
    self.test_count = test_count
    self.run_count = run_count
    self.thread_count = thread_count
    self.nameservers = nameservers
    self.results = {}
    self.status_callback = status_callback

  def msg(self, msg, **kwargs):
    if self.status_callback:
      self.status_callback(msg, **kwargs)

  def Run(self, test_records=None):
    """Manage and execute all tests on all nameservers.

    We used to run all tests for a nameserver, but the results proved to be
    unfair if the bandwidth was suddenly constrained. We now run a test on
    each server before moving on to the next.

    Returns:
      results: A dictionary of results
    """
    for test_run in range(self.run_count):
      input_queue = Queue.Queue()
      shuffled_records = {}

      # Pre-compute the shuffled test records per-nameserver to avoid thread
      # contention.
      for ns in self.nameservers.enabled:
        random.shuffle(test_records)
        shuffled_records[ns] = list(test_records)
        
        if ns not in self.results:
          self.results[ns] = []
          for x in range(self.run_count):
            self.results[ns].append([])

      for i in range(len(test_records)):
        for ns in self.nameservers.enabled:
          (request_type, hostname) = shuffled_records[ns][i]
          input_queue.put((ns, request_type, hostname))

      results_queue = self._LaunchBenchmarkThreads(input_queue)
      while results_queue.qsize():
        (ns, request_type, hostname, response, duration, error_msg) = results_queue.get()
        if error_msg:
          duration = ns.timeout
        self.results[ns][test_run].append((hostname, request_type, duration,
                                           response, error_msg))
    return self.results

  def _LaunchBenchmarkThreads(self, input_queue):
    """Launch and manage the benchmark threads."""
    results_queue = Queue.Queue()
    expected_total = input_queue.qsize()
    threads = []
    for unused_thread_num in range(0, self.thread_count):
      thread = BenchmarkThreads(input_queue, results_queue)
      thread.start()
      threads.append(thread)

    query_count = expected_total / len(self.nameservers.enabled)
    status_message = ('Sending %s queries to %s servers [%s threads]' %
                      (query_count, len(self.nameservers.enabled), self.thread_count))
    while results_queue.qsize() != expected_total:
      self.msg(status_message, count=results_queue.qsize(), total=expected_total)
      time.sleep(0.5)

    self.msg(status_message, count=results_queue.qsize(), total=expected_total)
    for thread in threads:
      thread.join()
    return results_queue

