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
import os.path
import re
import StringIO
import tempfile

import third_party

# from third_party
import httplib2

import data_sources
import util
import addr_util
import version

TRUNK_URL = 'http://namebench.googlecode.com/svn/trunk/'


def GetConfigurationAndSuppliedServers(filename='config/namebench.cfg'):
  """Get all of our configuration setup, args and config file."""
  (options, args) = DefineAndParseOptions(filename=filename)
  configured_options = ProcessConfigurationFile(options)
  supplied_ns = addr_util.ExtractIPTuplesFromString(' '.join(args))
  return (configured_options, supplied_ns)


def DefineAndParseOptions(filename):
  """Get our option configuration setup.

  Args:
    filename: path to configuration (may be relative)

  Returns:
    stuple of (OptionParser object, args)
  """
  ds = data_sources.DataSources()
  import_types = ds.ListSourceTypes()
  parser = optparse.OptionParser()
  parser.add_option('-r', '--runs', dest='run_count', default=1, type='int',
                    help='Number of test runs to perform on each nameserver.')
  parser.add_option('-z', '--config', dest='config', default=filename,
                    help='Config file to use.')
  parser.add_option('-o', '--output', dest='output_file', default=None,
                    help='Filename to write output to')
  parser.add_option('-t', '--template', dest='template', default='html',
                    help='Template to use for output generation (ascii, html, resolv.conf)')
  parser.add_option('-c', '--csv_output', dest='csv_file', default=None,
                    help='Filename to write query details to (CSV)')
  parser.add_option('-j', '--health_threads', dest='health_thread_count', type='int',
                    help='# of health check threads to use')
  parser.add_option('-J', '--benchmark_threads', dest='benchmark_thread_count', type='int',
                    help='# of benchmark threads to use')
  parser.add_option('-P', '--ping_timeout', dest='ping_timeout', type='float',
                    help='# of seconds ping requests timeout in.')
  parser.add_option('-y', '--timeout', dest='timeout', type='float',
                    help='# of seconds general requests timeout in.')
  parser.add_option('-Y', '--health_timeout', dest='health_timeout',
                    type='float', help='health check timeout (in seconds)')
  parser.add_option('-i', '--input', dest='input_source',
                    help=('Import hostnames from an filename or application (%s)' %
                          ', '.join(import_types)))
  parser.add_option('-I', '--invalidate_cache', dest='invalidate_cache',
                    action='store_true',
                    help='Force health cache to be invalidated')
  parser.add_option('-q', '--query_count', dest='query_count', type='int',
                    help='Number of queries per run.')
  parser.add_option('-m', '--select_mode', dest='select_mode',
                    default='automatic',
                    help='Selection algorithm to use (weighted, random, chunk)')
  parser.add_option('-s', '--num_servers', dest='num_servers',
                    type='int', help='Number of nameservers to include in test')
  parser.add_option('-S', '--system_only', dest='system_only',
                    action='store_true', help='Only test current system nameservers.')
  parser.add_option('-w', '--open_webbrowser', dest='open_webbrowser',
                    action='store_true', help='Opens the final report in your browser')
  parser.add_option('-u', '--upload_results', dest='upload_results',
                    action='store_true', help='Upload anonymized results to SITE_URL (False)')
  parser.add_option('-U', '--site_url', dest='site_url',
                    help='URL to upload results to (http://namebench.appspot.com/)')
  parser.add_option('-H', '--hide_results', dest='hide_results', action='store_true',
                    help='Upload results, but keep them hidden from indexes.')
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
  return GetLatestConfig('config/hostname_reference.cfg')

def GetLocalSanityChecks():
  return _GetLocalConfig('config/hostname_reference.cfg')

def GetNameServerList():
  raw_data = GetLatestConfig('config/servers.cfg')

def GetLocalNameServerList():
  return _ParseNameServerListing(_GetLocalConfig('config/servers.cfg'))

def _ParseNameServerListing(ns_config):
  nameservers = {}
  for label in ns_config:
    for ip, desc in ns_config[label]:
      # Convert IPv6 addresses back into a usable form.
      ip = ip.replace('_', ':')
      nameservers[ip] = _ParseServerValue(desc)
      nameservers[ip]['labels'].add(label)
  return nameservers

def _GetLocalConfig(conf_file):
  local_config = _ReadConfigFile(conf_file)
  return _ExpandConfigSections(local_config)

def _ReadConfigFile(conf_file):
  ref_file = util.FindDataFile(conf_file)
  local_config = ConfigParser.ConfigParser()
  local_config.read(ref_file)
  return local_config

def _ParseServerValue(value):
  """Why on earth did I make something so fugly."""
  # Example:
  # 129.250.35.251=NTT (2)    # y.ns.gin,39.569,-104.8582 (Englewood/CO/US)
  if '#' in value:
    name, comment = value.split('#')[0:2]
  else:
    name = value
    comment = ''
  name = name.rstrip()
  matches = re.match('(.*?) \((\w+)\)', name)
  if matches:
    service, instance = matches.groups()
  else:
    service = name
    instance = None

  matches = re.search('(\w.*?),([-\.\d]+),([-\.\d]+) \(.*?(\w+)\)(.*)', comment)
  if matches:
    hostname, lat, lon, country_code, notes = matches.groups()
  else:
    lat = lon = country_code = hostname = None
    notes = ''

  return {
    'name': name,
    'service': service,
    'instance': instance,
    'lat': lat,
    'lon': lon,
    'notes': notes.rstrip().lstrip().split('http')[0],
    'hostname': hostname,
    'labels': set(),
    'country_code': country_code
  }

def GetLatestConfig(conf_file):
  """Get the latest copy of the config file"""

  local_config = _ReadConfigFile(conf_file)
  download_latest = int(local_config.get('config', 'download_latest'))
  local_version = int(local_config.get('config', 'version'))
  
  if download_latest == 0:
    return _ExpandConfigSections(local_config)
    
  h = httplib2.Http(tempfile.gettempdir(), timeout=10)
  url = '%s/%s' % (TRUNK_URL, conf_file)
  content = None
  try:
    unused_resp, content = h.request(url, 'GET')
    remote_config = ConfigParser.ConfigParser()
  except:
    print '* Unable to fetch remote %s: %s' % (conf_file, util.GetLastExceptionString())
    return _ExpandConfigSections(local_config)

  if content and '[config]' in content:
    fp = StringIO.StringIO(content)
    try:
      remote_config.readfp(fp)
    except:
      print '* Unable to read remote %s: %s' % (conf_file, util.GetLastExceptionString())
      return _ExpandConfigSections(local_config)

  if int(remote_config.get('config', 'version')) > local_version:
    print '- Using %s' % url
    return _ExpandConfigSections(remote_config)
  else:
    return _ExpandConfigSections(local_config)

def _ExpandConfigSections(config):
  return dict([ (y, config.items(y)) for y in config.sections() if y != 'config' ])

def ProcessConfigurationFile(options):
  """Process configuration file, merge configuration with OptionParser.

  Args:
    options: optparse.OptionParser() object

  Returns:
    options: optparse.OptionParser() object
    global_ns: A list of global nameserver tuples.
    regional_ns: A list of regional nameservers tuples.

  Raises:
    ValueError: If we are unable to find a usable configuration file.
  """
  config = ConfigParser.ConfigParser()
  full_path = util.FindDataFile(options.config)
  config.read(full_path)
  if not config or not config.has_section('general'):
    raise ValueError('Could not find usable configuration in %s (%s)' % (full_path, options.config))
  general = dict(config.items('general'))

  if options.only or options.system_only:
    global_ns = []
    regional_ns = []
  else:
    global_ns = config.items('global')
    regional_ns = config.items('regional') + config.items('private')

  # -U implies -u
  if options.site_url:
    options.upload_results = True

  for option in general:
    if not getattr(options, option, None):
      if 'timeout' in option:
        value = float(general[option])
      elif 'count' in option or 'num' in option or 'hide' in option:
        value = int(general[option])
      else:
        value = general[option]
      setattr(options, option, value)

  for key in ('input_file', 'output_file', 'csv_file', 'input_source'):
    value = getattr(options, key, None)
    if value:
      setattr(options, key, os.path.expanduser(value))

  options.version = version.VERSION

  return (options, global_ns, regional_ns)

if __name__ == '__main__':
  print GetLocalNameServerList()
