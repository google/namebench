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

import ConfigParser
import optparse
import sys
import tempfile
import datetime

# Make it easy to import 3rd party utilities without editing their imports.
sys.path.append('lib/third_party')

from lib import benchmark
from lib import nameserver_list
from lib import util
from lib import web

VERSION = '0.6.5'

# Detect congestion problems early!
EXPECTED_DURATION = 50.0
SEVERE_CONGESTION_MULTIPLIER = 6.0

def processConfiguration(opt):
  # Read the config file, set variables
  config = ConfigParser.ConfigParser()
  config.read(opt.config)
  general = dict(config.items('general'))
  primary_ns = config.items('primary')
  secondary_ns = config.items('secondary')

  # Set some important defaults.
  for option in ('thread_count', 'timeout', 'health_timeout', 'num_servers'):
    if not getattr(opt, option):
      setattr(opt, option, float(general[option]))

  # Include internal & global first
  if opt.thread_count:
    thread_count = int(opt.thread_count)
  else:
    thread_count = int(general['max_thread_count'])

  return (opt, primary_ns, secondary_ns)

if __name__ == '__main__':
  print 'namebench %s - %s' % (VERSION, datetime.datetime.now())

  parser = optparse.OptionParser()
#  parser.add_option('-g', '--gui', dest='gui', default=False,
#                    action='store_true',
#                    help='Use graphical user interface (EXPERIMENTAL)')
  parser.add_option('-r', '--runs', dest='run_count', default=2, type='int',
                    help='Number of test runs to perform on each nameserver.')
  parser.add_option('-c', '--config', dest='config', default='namebench.cfg',
                    help='Config file to use.')
  parser.add_option('-o', '--output', dest='output_file',
                    help='Filename to write query results to (CSV format).')
  parser.add_option('-j', '--threads', dest='thread_count',
                    help='# of threads to use')
  parser.add_option('-y', '--timeout', dest='timeout', type='float',
                    help='# of seconds general requests timeout in.')
  parser.add_option('-Y', '--health_timeout', dest='health_timeout',
                    type='float', help='# of seconds health checks timeout in.')
  parser.add_option('-i', '--input', dest='input_file',
                    default='data/top-10000.txt',
                    help='File containing a list of domain names to query.')
  parser.add_option('-t', '--tests', dest='test_count', default=40, type='int',
                    help='Number of queries per run.')
  parser.add_option('-s', '--num_servers', dest='num_servers',
                    type='int', help='Number of nameservers to include in test')
  (cli_options, args) = parser.parse_args()
  (opt, primary_ns, secondary_ns) = processConfiguration(cli_options)

  print ('threads=%s tests=%s runs=%s timeout=%s health_timeout=%s servers=%s' %
         (opt.thread_count, opt.test_count, opt.run_count, opt.timeout,
          opt.health_timeout, opt.num_servers))
  print '-' * 78

  for arg in args:
    if '.' in arg:
      primary_ns.append((arg, arg))


  (intercepted, duration) = util.AreDNSPacketsIntercepted()
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
    print '* WOAH! Intercept check completed in %sms (%.1fX slower than normal)' % (duration, congestion)
    print '* NOTE: results may be inconsistent if your connection is saturated!'
    print ''

  nameservers = nameserver_list.NameServers(primary_ns, secondary_ns,
                                            include_internal=True,
                                            timeout=opt.timeout,
                                            health_timeout=opt.health_timeout,
                                            version=VERSION)
  nameservers.thread_count = int(opt.thread_count)
  nameservers.cache_dir = tempfile.gettempdir()
  nameservers.FilterUnwantedServers(count=int(opt.num_servers))
  print ''
  print 'Final list of nameservers to benchmark:'
  print '---------------------------------------'
  for ns in nameservers:
    print '  %s [%s], health tests took %sms' % (ns.ip, ns.name,
                                                 ns.check_duration)

  bmark = benchmark.NameBench(nameservers, opt.input_file,
                              run_count=opt.run_count,
                              test_count=opt.test_count)
  bmark.Run()
  bmark.DisplayResults()
  if opt.output_file:
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
