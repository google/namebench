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

import datetime
import sys
import tempfile
from lib import benchmark
from lib import config
from lib import history_parser
from lib import nameserver_list
from lib import conn_quality

VERSION = '0.9.1'

class NameBenchCli(object):
  def __init__(self, options, primary_ns, secondary_ns):
    self.options = options
    self.primary_ns = primary_ns
    self.secondary_ns = secondary_ns

  def msg(self, msg, count=None, total=None, error=False):
    if error:
      print
      print '* ERROR: %s' % msg
      sys.exit(2)
    elif not total:
      print '- %s' % msg
    elif count == 1:
      sys.stdout.write('- %s: %s/%s' % (msg, count, total))
    elif count == total:
      sys.stdout.write('%s/%s\n' % (count, total))
    else:
      sys.stdout.write('.')
    sys.stdout.flush()

  def PrepareNameservers(self):
    include_internal = True
    if self.options.only:
      include_internal = False
      if not self.primary_ns:
        print 'If you use --only, you must provide nameservers to use.'
        sys.exit(1)

    nameservers = nameserver_list.NameServers(
        self.primary_ns, self.secondary_ns,
        num_servers=self.options.num_servers,
        include_internal=include_internal,
        timeout=self.options.timeout,
        health_timeout=self.options.health_timeout,
        status_callback=self.msg
    )
    nameservers.CheckHealth()
    print ''
    print 'Final list of nameservers considered:'
    print '-' * 78
    for n in nameservers.SortByFastest():
      print '%-15.15s %-16.16s %-4.0fms | %s' % (n.ip, n.name, n.check_duration,
                                               n.warnings_string)
    print ''
    return nameservers

  def PrepareBenchmark(self, nameservers):
    if self.options.import_file:
      importer = history_parser.HistoryParser()
      history = importer.Parse(self.options.import_file)
      if history:
        print '- Imported %s records from %s' % (len(history), self.options.import_file)
      else:
        print '- Could not import anything from %s' % self.options.import_file
        sys.exit(2)
    else:
      history = None

    bmark = benchmark.Benchmark(nameservers,
                                run_count=self.options.run_count,
                                test_count=self.options.test_count,
                                status_callback=self.msg)
    if history:
      bmark.CreateTests(history, select_mode=self.options.select_mode)
    else:
      bmark.CreateTestsFromFile(self.options.data_file, select_mode=self.options.select_mode)

    return bmark

  def Execute(self):
    print('namebench %s - %s (%s) on %s' %
          (VERSION, self.options.import_file or self.options.data_file, self.options.select_mode,
           datetime.datetime.now()))
    print ('threads=%s tests=%s runs=%s timeout=%s health_timeout=%s servers=%s' %
           (self.options.thread_count, self.options.test_count, self.options.run_count, self.options.timeout,
            self.options.health_timeout, self.options.num_servers))
    print '-' * 78

    nameservers = self.PrepareNameservers()
    bmark = self.PrepareBenchmark(nameservers)
    bmark.Run()
    print ''
    print bmark.CreateReport(format='ascii')
    if self.options.output_file:
      f = open(self.options.output_file, 'w')
      print '* Saving report to %s (%s)' % (self.options.output_file,
                                            self.options.output_format)
      f.write(bmark.CreateReport(format=self.options.output_format))
      f.close()

    if self.options.csv_file:
      print ''
      print '* Saving request details to %s' % self.options.csv_file
      bmark.SaveResultsToCsv(self.options.output_file)


if __name__ == '__main__':
  (options, primary, secondary) = config.GetConfiguration()
  cli = NameBenchCli(options, primary, secondary)
  cli.Execute()
