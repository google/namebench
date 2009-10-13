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
import optparse
import sys
import tempfile
from lib import benchmark
from lib import config
from lib import history_parser
from lib import nameserver_list
from lib import conn_quality

VERSION = '0.8.9'

class NameBenchCli(object):
  def __init__(self, cli_options, args):
    (self.options, self.primary_ns, self.secondary_ns) = config.ProcessConfiguration(cli_options)
    for arg in args:
      if '.' in arg:
        self.primary_ns.append((arg, arg))

  def msg(self, msg, count=None, total=None):
    if not total:
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
    cq = conn_quality.ConnectionQuality()
    (intercepted, congestion, duration) = cq.CheckConnectionQuality()

    if intercepted:
      print 'XXX[ OHNO! ]XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
      print 'XX Someone upstream of this machine is doing evil things and  XX'
      print 'XX intercepting all outgoing nameserver requests. The results XX'
      print 'XX of this program will be useless. Get your ISP to fix it.   XX'
      print 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
      print ''
    if congestion > 1:
      nameservers.ApplyCongestionFactor(congestion)
      print('- Congestion connection detected (%.1fX slower than expected), '
            'timeouts increased to (%.1fms,%.1fms)' %
            (congestion, nameservers.timeout, nameservers.health_timeout))
    else:
      print('- Connection looks healthy, check duration took %.0fms' % duration)
    if len(nameservers) > 1:
      nameservers.thread_count = int(self.options.thread_count)
      nameservers.cache_dir = tempfile.gettempdir()
      nameservers.FindAndRemoveUndesirables()
    print ''
    print 'Final list of nameservers to benchmark:'
    print '-' * 78
    for ns in nameservers.SortByFastest():
      if ns.warnings:
        add_text = '# ' + ', '.join(ns.warnings)
      else:
        add_text = ''
      print '%-15.15s %-16.16s %-4.0fms %s' % (ns.ip, ns.name, ns.check_duration, add_text)
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
    print bmark.CreateReport()
    if self.options.output_file:
      print ''
      print '* Saving detailed results to %s' % self.options.output_file
      bmark.SaveResultsToCsv(self.options.output_file)


if __name__ == '__main__':
  parser = optparse.OptionParser()
  parser.add_option('-r', '--runs', dest='run_count', default=1, type='int',
                    help='Number of test runs to perform on each nameserver.')
  parser.add_option('-c', '--config', dest='config', default='namebench.cfg',
                    help='Config file to use.')
  parser.add_option('-o', '--output', dest='output_file', default='output.csv',
                    help='Filename to write query results to (CSV format).')
  parser.add_option('-j', '--threads', dest='thread_count',
                    help='# of threads to use')
  parser.add_option('-y', '--timeout', dest='timeout', type='float',
                    help='# of seconds general requests timeout in.')
  parser.add_option('-Y', '--health_timeout', dest='health_timeout',
                    type='float', help='health check timeout (in seconds)')
  parser.add_option('-f', '--filename', dest='data_file',
                    default='data/alexa-top-10000-global.txt',
                    help='File containing a list of domain names to query.')
  parser.add_option('-i', '--import', dest='import_file',
                    help=('Import history from safari, google_chrome, '
                          'internet_explorer, opera, squid, or a file path.'))
  parser.add_option('-t', '--tests', dest='test_count', type='int',
                    help='Number of queries per run.')
  parser.add_option('-x', '--select_mode', dest='select_mode',
                    default='weighted',
                    help='Selection algorithm to use (weighted, random, chunk)')
  parser.add_option('-s', '--num_servers', dest='num_servers',
                    type='int', help='Number of nameservers to include in test')
  parser.add_option('-S', '--no_secondary', dest='no_secondary',
                    action='store_true', help='Disable secondary servers')
  parser.add_option('-O', '--only', dest='only',
                    action='store_true',
                    help='Only test nameservers passed as arguments')
  (options, args) = parser.parse_args()
  cli = NameBenchCli(options, args)
  cli.Execute()
