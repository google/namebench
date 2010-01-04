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

import ConfigParser
import optparse
import StringIO
import tempfile

# from third_party
import httplib2

import history_parser
import util
import version

SANITY_REFERENCE_URL = 'http://namebench.googlecode.com/svn/trunk/data/hostname_reference.cfg'


def GetConfiguration(filename='namebench.cfg'):
  (options, args) = DefineAndParseOptions(filename=filename)
  (configured_options, global_ns, regional_ns) = ProcessConfigurationFile(options)
  supplied_ns = util.ExtractIPTuplesFromString(' '.join(args))
  return (configured_options, supplied_ns, global_ns, regional_ns)

def DefineAndParseOptions(filename='namebench.cfg'):
  """Get our option configuration setup.

  Returns: tuple of (OptionParser object, args)
  """
  h = history_parser.HistoryParser()
  import_types = sorted(h.GetTypes().keys())
  parser = optparse.OptionParser()
  parser.add_option('-r', '--runs', dest='run_count', default=1, type='int',
                    help='Number of test runs to perform on each nameserver.')
  parser.add_option('-z', '--config', dest='config', default=filename,
                    help='Config file to use.')
  parser.add_option('-o', '--output', dest='output_file', default=None,
                    help='Filename to write HTML output to')
  parser.add_option('-c', '--csv_output', dest='csv_file', default=None,
                    help='Filename to write CSV output to')
  parser.add_option('-j', '--threads', dest='thread_count', type='int',
                    help='# of threads to use')
  parser.add_option('-y', '--timeout', dest='timeout', type='float',
                    help='# of seconds general requests timeout in.')
  parser.add_option('-Y', '--health_timeout', dest='health_timeout',
                    type='float', help='health check timeout (in seconds)')
  parser.add_option('-d', '--datafile', dest='data_file',
                    default='data/alexa-top-10000-global.txt',
                    help='File containing a list of domain names to query.')
  parser.add_option('-i', '--import', dest='import_source',
                    help=('Import history from an external application (%s)' %
                          ', '.join(import_types)))
  parser.add_option('-I', '--invalidate_cache', dest='invalidate_cache',
                    action='store_true',
                    help='Force health cache to be invalidated')
  parser.add_option('-t', '--tests', dest='test_count', type='int',
                    help='Number of queries per run.')
  parser.add_option('-m', '--select_mode', dest='select_mode',
                    default='weighted',
                    help='Selection algorithm to use (weighted, random, chunk)')
  parser.add_option('-s', '--num_servers', dest='num_servers',
                    type='int', help='Number of nameservers to include in test')
  parser.add_option('-S', '--no_regional', dest='no_regional',
                    action='store_true', help='Disable regional_ns servers')
  parser.add_option('-w', '--open_webbrowser', dest='open_webbrowser',
                    action='store_true', help='Opens the final report in your browser')
  parser.add_option('-x', '--no_gui', dest='no_gui',
                    action='store_true', help='Disable GUI')
  parser.add_option('-C', '--enable-censorship-checks', dest='enable_censorship_checks',
                    action='store_true', help='Enable censorship checks')
  parser.add_option('-6', '--ipv6_only', dest='ipv6_only',
                    action='store_true', help='Only include IPv6 name servers')
  # Silly Mac OS X adding -psn_0_xxxx
  parser.add_option('-p', '--psn')
  parser.add_option('-O', '--only', dest='only',
                    action='store_true',
                    help='Only test nameservers passed as arguments')
  return parser.parse_args()

def GetLatestSanityChecks():
  """Get the latest copy of the sanity checks config."""
  h = httplib2.Http(tempfile.gettempdir(), timeout=10)
  try:
    resp, content = h.request(SANITY_REFERENCE_URL, 'GET')
  except exc:
    print exc
  config = ConfigParser.ConfigParser()

  if '[sanity]' in content:
    fp = StringIO.StringIO(content)
    try:
      config.readfp(fp)
    except:
      pass

  if not config.has_section('sanity') or not config.has_section('censorship'):
    ref_file = util.FindDataFile('data/hostname_reference.cfg')
    print '- Using built-in sanity reference: %s' % ref_file
    config.read(ref_file)

  return (config.items('sanity'), config.items('sanity-secondary'), config.items('censorship'))


def ProcessConfigurationFile(options):
  """Process configuration file, merge configuration with OptionParser.

  Args:
    options: optparse.OptionParser() object

  Returns:
    options: optparse.OptionParser() object
    global_ns: A list of global nameserver tuples.
    regional_ns: A list of regional nameservers tuples.
  """
  config = ConfigParser.ConfigParser()
  config.read(util.FindDataFile(options.config))
  general = dict(config.items('general'))

  if options.only:
    global_ns = []
    regional_ns = []
  else:
    global_ns = config.items('global')
    regional_ns = config.items('regional') + config.items('private')

  if options.no_regional:
    regional_ns = []

  for option in general:
    if not getattr(options, option):
      if 'timeout' in option:
        value = float(general[option])
      elif 'count' in option or 'num' in option:
        value = int(general[option])
      else:
        value = general[option]
      setattr(options, option, value)

  options.version = version.VERSION
  return (options, global_ns, regional_ns)
