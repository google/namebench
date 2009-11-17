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

def GenerateOutputFilename(extension):
#  output_dir = os.path.join(os.getenv('HOME'), 'Desktop')
  output_dir = tempfile.gettempdir()
  output_base = 'namebench_%s' % datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d %H%M')
  output_base = output_base.replace(':', '').replace(' ', '_')
  return os.path.join(output_dir, '%s.%s' % (output_base, extension))

class BaseUI(object):
  """Common methods for UI implementations."""

  def UpdateStatus(self, UpdateStatus, count=None, total=None, error=None):
    """Update the little status message on the bottom of the window."""
    if hasattr(self, 'status_callback') and self.status_callback:
      self.status_callback(UpdateStatus, count=count, total=total)
    else:
      print '(UpdateStatus: %s count=%s total=%s, err=%s)' % (UpdateStatus, count, total, error)

  def PrepareBenchmark(self):
    self.UpdateStatus('Building nameserver objects')
    self.nameservers = nameserver_list.NameServers(
        self.primary,
        self.secondary,
        num_servers=self.options.num_servers,
        timeout=self.options.timeout,
        health_timeout=self.options.health_timeout,
        status_callback=self.UpdateStatus
    )

    self.nameservers.cache_dir = tempfile.gettempdir()
    if len(self.nameservers) > 1:
      self.nameservers.thread_count = int(self.options.thread_count)
      self.nameservers.cache_dir = tempfile.gettempdir()

    self.UpdateStatus('Checking nameserver health')
    self.nameservers.CheckHealth()
    self.bmark = benchmark.Benchmark(self.nameservers,
                                     test_count=self.options.test_count,
                                     run_count=self.options.run_count,
                                     status_callback=self.UpdateStatus)
    self.bmark.UpdateStatus = self.UpdateStatus
    self.UpdateStatus('Creating test records using %s' % self.options.select_mode)
    if self.options.data_source:
      hosts = self.hparser.GetParsedSource(self.options.data_source)
      self.UpdateStatus('%s has %s hosts' % (self.options.data_source, len(hosts)))
      test_data = self.hparser.GenerateTestData(hosts)
      self.UpdateStatus('%s records available in test pool' % len(test_data))
      self.bmark.CreateTests(test_data, select_mode=self.options.select_mode)
    else:
      # The Alexa data (by default)
      data_path = os.path.join(self.resource_dir, self.options.data_file)
      self.bmark.CreateTestsFromFile(data_path,
                                     select_mode=self.options.select_mode)
    self.UpdateStatus('Benchmark preparation is complete.')

  def RunBenchmark(self):
    self.UpdateStatus('Running the benchmark')
    self.bmark.Run()
    self.UpdateStatus('Calculating the best nameserver')
    best = self.bmark.BestOverallNameServer()
    self.CreateReports()
    self.DisplayHtmlReport()
    self.UpdateStatus('Complete! %s [%s] is the best.' % (best.name, best.ip))

  def CreateReports(self):
    """Create CSV & HTML reports for the latest run."""
    self.html_path = GenerateOutputFilename('html')
    self.csv_path = GenerateOutputFilename('csv')

    self.UpdateStatus('Saving HTML report')
    f = open(self.html_path, 'w')
    self.bmark.CreateReport(format='html', output_fp=f, config=self.options, csv_path=self.csv_path)
    f.close()

    self.UpdateStatus('Saving query details (CSV)')
    self.bmark.SaveResultsToCsv(self.csv_path)
    self.UpdateStatus('Reports saved.')

  def DisplayHtmlReport(self):
    self.UpdateStatus('Opening %s' % self.html_path)
    webbrowser.open(self.html_path)

  def DiscoverSources(self):
    """Seek out and create a list of valid data sources."""
    self.UpdateStatus('Searching for usable data sources')
    self.hparser = history_parser.HistoryParser()
    self.sources = self.hparser.GetAvailableHistorySources()
    self.UpdateStatus('All available sources have been parsed.')

  def ParseSourceSelection(self, selection):
    self.UpdateStatus('Matching "%s" to %s' % (selection, self.sources))
    for source in self.sources:
      parsed_name = history_parser.sourceToTitle(source)
      if parsed_name.lower() == selection.lower():
        src_type = source[0]
        self.UpdateStatus('Parsed source type to %s' % src_type)
        return src_type
    self.UpdateStatus('Unable to match "%s" to a source type' % selection)
    return None

