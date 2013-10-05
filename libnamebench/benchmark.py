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

import Queue
import random
import threading
import time


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
        # We've moved this here so that it's after all of the random selection goes through.
        if '__RANDOM__' in hostname:
          hostname = hostname.replace('__RANDOM__', str(random.random() * random.randint(0, 99999)))

        (response, duration, error_msg) = ns.TimedRequest(request_type, hostname)
        self.results.put((ns, request_type, hostname, response, duration, error_msg))
      except Queue.Empty:
        return


class Benchmark(object):
  """The main benchmarking class."""

  def __init__(self, nameservers, run_count=2, query_count=30, thread_count=1,
               status_callback=None):
    """Constructor.

    Args:
      nameservers: a list of NameServerData objects
      run_count: How many test-runs to perform on each nameserver (int)
      query_count: How many DNS lookups to test in each test-run (int)
      thread_count: How many benchmark threads to use (int)
      status_callback: Where to send msg() updates to.
    """
    self.query_count = query_count
    self.run_count = run_count
    self.thread_count = thread_count
    self.nameservers = nameservers
    self.results = {}
    self.status_callback = status_callback

  def msg(self, msg, **kwargs):
    if self.status_callback:
      self.status_callback(msg, **kwargs)

  def _CheckForIndexHostsInResults(self, test_records):
    """Check if we have already tested index hosts.

    Args:
      test_records: List of tuples of test records (type, record)

    Returns:
      A list of results that have already been tested
      A list of records that still need to be tested.
    """
    needs_test = []
    index_results = {}
    for test in test_records:
      matched = False
      for ns in self.results:
        for result in self.results[ns][0]:
          hostname, request_type = result[0:2]
          if (request_type, hostname) == test:
            matched = True
            index_results.setdefault(ns, []).append(result)
            # So that we don't include the second results if duplicates exist.
            break
      if not matched:
        needs_test.append(test)
    return (index_results, needs_test)

  def RunIndex(self, test_records):
    """Run index tests using the same mechanism as a standard benchmark."""
    if not test_records:
      print 'No records to test.'
      return None

    index_results, pending_tests = self._CheckForIndexHostsInResults(test_records)
    run_results = self._SingleTestRun(pending_tests)
    for ns in run_results:
      index_results.setdefault(ns, []).extend(run_results[ns])
    return index_results

  def Run(self, test_records=None):
    """Run all test runs for all nameservers."""

    # We don't want to keep stats on how many queries timed out from previous runs.
    for ns in self.nameservers.enabled:
      ns.ResetErrorCounts()

    for _ in range(self.run_count):
      run_results = self._SingleTestRun(test_records)
      for ns in run_results:
        self.results.setdefault(ns, []).append(run_results[ns])
    return self.results

  def _SingleTestRun(self, test_records):
    """Manage and execute a single test-run on all nameservers.

    We used to run all tests for a nameserver, but the results proved to be
    unfair if the bandwidth was suddenly constrained. We now run a test on
    each server before moving on to the next.

    Args:
      test_records: a list of tuples in the form of (request_type, hostname)

    Returns:
      results: A dictionary of tuples, keyed by nameserver.
    """
    input_queue = Queue.Queue()
    shuffled_records = {}
    results = {}
    # Pre-compute the shuffled test records per-nameserver to avoid thread
    # contention.
    for ns in self.nameservers.enabled:
      random.shuffle(test_records)
      shuffled_records[ns.ip] = list(test_records)

    # Feed the pre-computed records into the input queue.
    for i in range(len(test_records)):
      for ns in self.nameservers.enabled:
        (request_type, hostname) = shuffled_records[ns.ip][i]
        input_queue.put((ns, request_type, hostname))

    results_queue = self._LaunchBenchmarkThreads(input_queue)
    errors = []
    while results_queue.qsize():
      (ns, request_type, hostname, response, duration, error_msg) = results_queue.get()
      if error_msg:
        duration = ns.timeout * 1000
        errors.append((ns, error_msg))
      results.setdefault(ns, []).append((hostname, request_type, duration, response, error_msg))

    for (ns, error_msg) in errors:
      self.msg('Error querying %s: %s' % (ns, error_msg))
    return results

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
    status_message = ('Sending %s queries to %s servers' %
                      (query_count, len(self.nameservers.enabled)))
    while results_queue.qsize() != expected_total:
      self.msg(status_message, count=results_queue.qsize(), total=expected_total)
      time.sleep(0.5)

    self.msg(status_message, count=results_queue.qsize(), total=expected_total)
    for thread in threads:
      thread.join()
    return results_queue

