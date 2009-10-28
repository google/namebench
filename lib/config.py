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

"""Define and process configuration from command-line or config file."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import optparse
import ConfigParser
import history_parser

def GetConfiguration(filename='namebench.cfg'):
  (options, args) = DefineAndParseOptions(filename=filename)
  (configured_options, primary, secondary) = ProcessConfigurationFile(options)
  for arg in args:
    if '.' in arg:
      primary.append((arg, arg))
  return (configured_options, primary, secondary)

def DefineAndParseOptions(filename='namebench.cfg'):
  """Get our option configuration setup.

  Returns: tuple of (OptionParser object, args)
  """
  h = history_parser.HistoryParser()
  import_types = [x[0] for x in h.GetTypes()]

  # TODO(tstromberg): Add option to force health cache invalidation.

  parser = optparse.OptionParser()
  parser.add_option('-r', '--runs', dest='run_count', default=1, type='int',
                    help='Number of test runs to perform on each nameserver.')
  parser.add_option('-z', '--config', dest='config', default=filename,
                    help='Config file to use.')
  parser.add_option('-o', '--output', dest='output_file', default=None,
                    help='Filename to write output to')
  parser.add_option('-f', '--format', dest='output_format', default='ascii',
                    help='Output format for file (ascii, html)')
  parser.add_option('-c', '--csv_output', dest='csv_file', default=None,
                    help='Filename to write CSV output to')
  parser.add_option('-j', '--threads', dest='thread_count',
                    help='# of threads to use')
  parser.add_option('-y', '--timeout', dest='timeout', type='float',
                    help='# of seconds general requests timeout in.')
  parser.add_option('-Y', '--health_timeout', dest='health_timeout',
                    type='float', help='health check timeout (in seconds)')
  parser.add_option('-d', '--datafile', dest='data_file',
                    default='data/alexa-top-10000-global.txt',
                    help='File containing a list of domain names to query.')
  parser.add_option('-i', '--import', dest='import_file',
                    help=('Import history from an external application (%s)' %
                          ', '.join(import_types)))
  parser.add_option('-t', '--tests', dest='test_count', type='int',
                    help='Number of queries per run.')
  parser.add_option('-x', '--select_mode', dest='select_mode',
                    default='weighted',
                    help='Selection algorithm to use (weighted, random, chunk)')
  parser.add_option('-s', '--num_servers', dest='num_servers',
                    type='int', help='Number of nameservers to include in test')
  parser.add_option('-S', '--no_secondary', dest='no_secondary',
                    action='store_true', help='Disable secondary servers')
  # Silly Mac OS X adding -psn_0_xxxx
  parser.add_option('-p', '--psn')
  parser.add_option('-O', '--only', dest='only',
                    action='store_true',
                    help='Only test nameservers passed as arguments')
  return parser.parse_args()

def ProcessConfigurationFile(options):
  """Process configuration file, merge configuration with OptionParser.

  Args:
    options: optparse.OptionParser() object

  Returns:
    options: optparse.OptionParser() object
    primary: A list of primary nameservers
    secondary: A list of secondary nameservers.
  """
  config = ConfigParser.ConfigParser()
  config.read(options.config)
  general = dict(config.items('general'))

  if options.only:
    primary = []
    secondary = []
  else:
    primary = config.items('primary')
    secondary = config.items('open') + config.items('closed')

  if options.no_secondary:
    secondary = []

  for option in general:
    if not getattr(options, option):
      if 'timeout' in option:
        value = float(general[option])
      elif 'count' in option or 'num' in option:
        value = int(general[option])
      else:
        value = general[option]
      setattr(options, option, value)

  return (options, primary, secondary)
