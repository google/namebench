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

"""Helpful things for user interfaces."""

import datetime
import os
import tempfile
import better_webbrowser

from . import benchmark
from . import config
from . import data_sources
from . import nameserver_list
from . import reporter
from . import site_connector
from . import util

__author__ = 'tstromberg@google.com (Thomas Stromberg)'


def GenerateOutputFilename(extension):
  output_dir = tempfile.gettempdir()
  output_base = 'namebench_%s' % datetime.datetime.strftime(datetime.datetime.now(),
                                                            '%Y-%m-%d %H%M')
  output_base = output_base.replace(':', '').replace(' ', '_')
  return os.path.join(output_dir, '%s.%s' % (output_base, extension))

class BaseUI(object):
  """Common methods for all UI implementations."""

  def __init__(self):
    self.reporter = None
    self.nameservers = None
    self.bmark = None
    self.html_path = None
    self.csv_path = None
    self.sources = {}
    self.test_records = []

  def UpdateStatus(self, msg, **kwargs):
    """Update the little status message on the bottom of the window."""
    if hasattr(self, 'status_callback') and self.status_callback:
      self.status_callback(msg, **kwargs)
    else:
      print msg

  def DebugMsg(self, message):
    self.UpdateStatus(message, debug=True)

  def LoadDataSources(self):
    self.data_src = data_sources.DataSources(status_callback=self.UpdateStatus)

  def PrepareTestRecords(self):
    if self.options.input_source:
      src_type = self.options.input_source
      src_name = self.data_src.GetNameForSource(src_type)
    else:
      (src_type, src_name) = self.data_src.GetBestSourceDetails()[:2]

    self.test_records = self.data_src.GetTestsFromSource(src_type,
                                                         self.options.query_count,
                                                         select_mode=self.options.select_mode)

  def PrepareNameServers(self):
    """Setup self.nameservers to have a list of healthy fast servers."""
    self.nameservers = nameserver_list.NameServers(
        self.preferred,
        self.secondary,
        include_internal=self.include_internal,
        num_servers=self.options.num_servers,
        timeout=self.options.timeout,
        ping_timeout=self.options.ping_timeout,
        health_timeout=self.options.health_timeout,
        ipv6_only=self.options.ipv6_only,
        status_callback=self.UpdateStatus
    )
    if self.options.invalidate_cache:
      self.nameservers.InvalidateSecondaryCache()

    self.nameservers.cache_dir = tempfile.gettempdir()

    # Don't waste time checking the health of the only nameserver in the list.
    if len(self.nameservers) > 1:
      self.nameservers.thread_count = int(self.options.health_thread_count)
      self.nameservers.cache_dir = tempfile.gettempdir()

    self.UpdateStatus('Checking latest sanity reference')
    (primary_checks, secondary_checks, censor_tests) = config.GetLatestSanityChecks()
    if not self.options.enable_censorship_checks:
      censor_tests = []
    else:
      self.UpdateStatus('Censorship checks enabled: %s found.' % len(censor_tests))

    self.UpdateStatus('Checking nameserver health')
    self.nameservers.CheckHealth(primary_checks, secondary_checks, censor_tests=censor_tests)

  def PrepareBenchmark(self):
    """Setup the benchmark object with the appropriate dataset."""
    if len(self.nameservers) == 1:
      thread_count = 1
    else:
      thread_count = self.options.benchmark_thread_count

    self.bmark = benchmark.Benchmark(self.nameservers,
                                     query_count=self.options.query_count,
                                     run_count=self.options.run_count,
                                     thread_count=thread_count,
                                     status_callback=self.UpdateStatus)

  def RunBenchmark(self):
    """Run the benchmark."""
    results = self.bmark.Run(self.test_records)
    index = []

    if self.options.upload_results:
      connector = site_connector.SiteConnector(self.options)
      try:
        index_hosts = connector.GetIndexHosts()
      except:
        index_hosts = []
        self.UpdateStatus("Failed to download index hosts: %s" % util.GetLastExceptionString())
      index = self.bmark.RunIndex(index_hosts)
      print index
    self.reporter = reporter.ReportGenerator(self.options, self.nameservers,
                                             results, index=index)

  def RunAndOpenReports(self):
    """Run the benchmark and open up the HTML report on completion."""
    self.RunBenchmark()
    best = self.reporter.BestOverallNameServer()
    self.CreateReports()
    self.DisplayHtmlReport()
    self.UpdateStatus('Complete! %s [%s] is the best.' % (best.name, best.ip))

  def CreateReports(self):
    """Create CSV & HTML reports for the latest run."""
    if self.options.output_file:
      self.html_path = self.options.output_file
    else:
      self.html_path = GenerateOutputFilename('html')

    if self.options.csv_file:
      self.csv_path = self.options_csv_file
    else:
      self.csv_path = GenerateOutputFilename('csv')

    if self.options.upload_results:
      try:
        json_data = self.reporter.CreateJsonData()
        connector = site_connector.SiteConnector(self.options)
        connector.UploadJsonResults(json_data)
      except:
        self.UpdateStatus("Failed to upload results: %s" % util.GetLastExceptionString())

    self.UpdateStatus('Saving HTML report to %s' % self.html_path)
    f = open(self.html_path, 'w')
    self.reporter.CreateReport(format='html', output_fp=f,
                               csv_path=self.csv_path)
    f.close()

    self.UpdateStatus('Saving detailed results to %s' % self.csv_path)
    self.reporter.SaveResultsToCsv(self.csv_path)

  def DisplayHtmlReport(self):
    self.UpdateStatus('Opening %s' % self.html_path)
    better_webbrowser.output = self.DebugMsg
    better_webbrowser.open(self.html_path)

