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
import urllib
import webbrowser

import benchmark
import history_parser
import nameserver_list

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

# Hack to locate the Alexa data
RSRC_DIR = None


class BaseUI(object):
  """Common methods for UI implementations."""

  def msg(self, msg, count=None, total=None, error=None):
    """Update the little status message on the bottom of the window."""
    if hasattr(self, 'status_callback') and self.status_callback:
      self.status_callback(msg, count=count, total=total)
    else:
      print '(msg: %s count=%s total=%s, err=%s)' % (msg, count, total, error)

  def PrepareBenchmark(self):
    self.msg('Building nameserver objects')
    self.nameservers = nameserver_list.NameServers(
        self.primary,
        self.secondary,
        num_servers=self.options.num_servers,
        timeout=self.options.timeout,
        health_timeout=self.options.health_timeout,
        status_callback=self.msg
    )

    self.nameservers.cache_dir = tempfile.gettempdir()
    if len(self.nameservers) > 1:
      self.nameservers.thread_count = int(self.options.thread_count)
      self.nameservers.cache_dir = tempfile.gettempdir()

    self.msg('Checking nameserver health')
    self.nameservers.CheckHealth()
    self.bmark = benchmark.Benchmark(self.nameservers,
                                     test_count=self.options.test_count,
                                     run_count=self.options.run_count,
                                     status_callback=self.msg)
    self.bmark.msg = self.msg
    self.msg('Creating test records using %s' % self.options.select_mode)
    if self.options.data_source:
      hosts = self.hparser.GetParsedSource(self.options.data_source)
      test_data = self.hparser.GenerateTestData(hosts)
      self.bmark.CreateTests(test_data, select_mode=self.options.select_mode)
    else:
      global_path = '%s/data/alexa-top-10000-global.txt' % self.resource_dir
      self.bmark.CreateTestsFromFile(global_path,
                                     select_mode=self.options.select_mode)

  def RunBenchmark(self):
    self.msg('Running...')
    self.bmark.Run()
    best = self.bmark.BestOverallNameServer()
    self.CreateReports()
    self.DisplayHtmlReport()
    self.msg('Complete! %s [%s] is the best.' % (best.name, best.ip))

  def CreateReports(self):
    """Create CSV & HTML reports for the latest run."""
    output_dir = os.path.join(os.getenv('HOME'), 'Desktop')
    output_base = 'namebench_%s' % datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d %H%m')

    self.html_path = os.path.join(output_dir, '%s.html' % output_base)
    self.msg('Saving report to %s' % self.html_path)
    f = open(self.html_path, 'w')
    self.bmark.CreateReport(format='html', output_fp=f)
    f.close()

    self.csv_path = os.path.join(output_dir, '%s.csv' % output_base)
    self.msg('Saving detailed results to %s' % self.csv_path)
    self.bmark.SaveResultsToCsv(self.csv_path)

  def DisplayHtmlReport(self):
    url = 'file://' + urllib.quote(self.html_path)
    self.msg('Opening %s' % url)
    webbrowser.open(url)

  def DiscoverSources(self):
    """Seek out and create a list of valid data sources."""
    self.UpdateStatus('Searching for usable data sources')
    self.hparser = history_parser.HistoryParser()
    self.sources = self.hparser.GetAvailableHistorySources()

  def ParseSourceSelection(self, selection):
    for source in self.sources:
      if history_parser.sourceToTitle(source) == selection:
        src_type = source[0]
        self.msg('Parsed source type to %s' % src_type)
        return src_type


