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
# Make it easy to import 3rd party utilities without editing their imports.
sys.path.append('lib/third_party')
from lib import benchmark
from lib import config
from lib import history_parser
from lib import nameserver_list
from lib import util

VERSION = '0.8.3'

# Detect congestion problems early!
EXPECTED_DURATION = 120.0
SEVERE_CONGESTION_MULTIPLIER = 3

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
  (cli_options, args) = parser.parse_args()
  (opt, primary_ns, secondary_ns) = config.ProcessConfiguration(cli_options)
  for arg in args:
    if '.' in arg:
      primary_ns.append((arg, arg))
  
  include_internal = True
  if opt.only:
    include_internal = False
    if not primary_ns:
      print 'If you use --only, you must provide nameservers to use.'
      sys.exit(1)

  print('namebench %s - %s (%s) on %s' %
        (VERSION, opt.import_file or opt.data_file, opt.select_mode,
         datetime.datetime.now()))
  print ('threads=%s tests=%s runs=%s timeout=%s health_timeout=%s servers=%s' %
         (opt.thread_count, opt.test_count, opt.run_count, opt.timeout,
          opt.health_timeout, opt.num_servers))
  print '-' * 78

  if opt.import_file:
    importer = history_parser.HistoryParser()
    history = importer.Parse(opt.import_file)
    if history:
      print '- Imported %s records from %s' % (len(history), opt.import_file)
    else:
      print '- Could not import anything from %s' % opt.import_file
      sys.exit(2)
  else:
    history = None

  nameservers = nameserver_list.NameServers(primary_ns, secondary_ns,
                                            num_servers=opt.num_servers,
                                            include_internal=include_internal,
                                            timeout=opt.timeout,
                                            health_timeout=opt.health_timeout)
  (intercepted, duration) = util.AreDNSPacketsIntercepted()
  print '- DNS Intercept test completed in %sms' % duration
  congestion = duration / EXPECTED_DURATION

  if intercepted:
    print 'XXX[ OHNO! ]XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
    print 'XX Someone upstream of this machine is doing evil things and  XX'
    print 'XX intercepting all outgoing nameserver requests. The results XX'
    print 'XX of this program will be useless. Get your ISP to fix it.   XX'
    print 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
    print ''
    sys.exit(1)
  elif congestion > SEVERE_CONGESTION_MULTIPLIER:
    print '* Health checks are running %.1fX slower than expected!' % congestion
    print '* NOTE: results may be inconsistent if your connection is saturated!'
    print ''
    nameservers.ApplyCongestionFactor(congestion / 2.5)

  if len(nameservers) > 1:
    nameservers.thread_count = int(opt.thread_count)
    nameservers.cache_dir = tempfile.gettempdir()
    nameservers.FindAndRemoveUndesirables()
  print ''
  print 'Final list of nameservers to benchmark:'
  print '-' * 60
  for ns in nameservers.SortByFastest():
    print ' %-19.19s %-20.20s (%sms)' % (ns.ip, ns.name, ns.check_duration)
  print ''
  bmark = benchmark.NameBench(nameservers,
                              run_count=opt.run_count,
                              test_count=opt.test_count)
  if history:
    bmark.CreateTests(history, select_mode=opt.select_mode)
  else:
    bmark.CreateTestsFromFile(opt.data_file, select_mode=opt.select_mode)

  bmark.Run()
  bmark.DisplayResults()
  if opt.output_file:
    print ''
    print '* Saving detailed results to %s' % opt.output_file
    bmark.SaveResultsToCsv(opt.output_file)

  best = bmark.BestOverallNameServer()
  nearest = [x for x in bmark.NearestNameServers(3) if x.ip != best.ip][0:2]

  print ''
  print 'Recommended Configuration (fastest + nearest):'
  print '----------------------------------------------'
  for ns in [best] + nearest:
    if ns.warnings:
      warning = '(%s)' % ', '.join(ns.warnings)
    else:
      warning = ''
    print 'nameserver %-15.15s # %s %s' % (ns.ip, ns.name, warning)
