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

"""Provides data sources to use for benchmarking."""

import glob
import os
import os.path
import random
import re
import sys
import time
import ConfigParser

# See if a third_party library exists -- use it if so.
try:
  import third_party
except ImportError:
  pass


# relative
from . import util
from . import selectors

# Pick the most accurate timer for a platform. Stolen from timeit.py:
if sys.platform[:3] == 'win':
  DEFAULT_TIMER = time.clock
else:
  DEFAULT_TIMER = time.time

GLOBAL_DATA_CACHE = {}
INTERNAL_RE = re.compile('^0|\.pro[md]|\.corp|\.bor|internal|dmz|intra|\.local$')
# ^.*[\w-]+\.[\w-]+\.[\w-]+\.[a-zA-Z]+\.$|^[\w-]+\.[\w-]{3,}\.[a-zA-Z]+\.$
FQDN_RE = re.compile('^.*\..*\..*\..*\.$|^.*\.[\w-]*\.\w{3,4}\.$|^[\w-]+\.[\w-]{4,}\.\w+\.')

IP_RE = re.compile('^[0-9.]$')
DEFAULT_CONFIG_PATH = "config/data_sources.cfg"
MAX_NON_UNIQUE_RECORD_COUNT = 500000
MAX_FILE_MTIME_AGE_DAYS = 60
MIN_FILE_SIZE = 10000
MIN_RECOMMENDED_RECORD_COUNT = 200
MAX_FQDN_SYNTHESIZE_PERCENT = 4

class DataSources(object):
  def __init__(self, config_path=DEFAULT_CONFIG_PATH, status_callback=None):
    global GLOBAL_DATA_CACHE
    self.source_cache = GLOBAL_DATA_CACHE
    self.source_config = {}
    self.status_callback = status_callback
    self._LoadConfigFromPath(config_path)

  def msg(self, msg, **kwargs):
    if self.status_callback:
      self.status_callback(msg, **kwargs)
    else:
      print '- %s' % msg

  def _LoadConfigFromPath(self, path):
    conf_file = util.FindDataFile('config/data_sources.cfg')
    config = ConfigParser.ConfigParser()
    config.read(conf_file)
    for section in config.sections():
      if section not in self.source_config:
        self.source_config[section] = {
          'name': None,
          'search_paths': set(),
          # Store whether or not this data source contains personal data
          'full_hostnames': True
        }

      for (key, value) in config.items(section):
        if key == 'name':
          self.source_config[section]['name'] = value
        else:
          self.source_config[section]['search_paths'].add(value)

  def ListSourceTypes(self):
    """Get a list of all data sources we know about."""
    return sorted(self.source_config.keys())

  def ListSourcesWithDetails(self):
    """Get a list of all data sources found with total counts.

    Returns:
      List of tuples in form of (short_name, full_name, full_hosts, # of entries)
    """
    for source in self.ListSourceTypes():
      self._GetHostsFromSource(source, min_file_size=MIN_FILE_SIZE,
                               max_mtime_age_days=MAX_FILE_MTIME_AGE_DAYS)

    details = []
    for source in self.source_cache:
      details.append((source,
                      self.source_config[source]['name'],
                      self.source_config[source]['full_hostnames'],
                      len(self.source_cache[source])))
    return sorted(details, key=lambda x:(x[2], x[3]), reverse=True)

  def GetBestSourceDetails(self):
    return self.ListSourcesWithDetails()[0]

  def GetNameForSource(self, source):
    if source in self.source_config:
      return self.source_config[source]['name']
    else:
      # Most likely a custom file path
      return source

  def GetCachedRecordCountForSource(self, source):
    return len(self.source_cache[source])

  def _CreateRecordsFromHostEntries(self, entries):
    """Create records from hosts, removing duplicate entries and IP's

    Args:
      A list of test-data entries.

    Returns:
      A tuple of (filtered records, full_host_names (Boolean)
    """
    self.msg('Generating test records for %s entries' % len(entries))
    real_tld_re = re.compile('[a-z]{2,4}$')
    internal_re = re.compile('^[\d:\.]+$')
    last_entry = None

    records = []
    full_host_count = 0
    for entry in entries:
      if entry == last_entry:
        continue
      else:
        last_entry = entry

      if ' ' in entry:
        (record_type, host) = entry.split(' ')
      else:
        record_type = 'A'
        host = entry

      if not IP_RE.match(host) and not INTERNAL_RE.search(host):
        if not host.endswith('.'):
          # For a short string like this, simple addition is 54% faster than formatting
          host = host + '.'
        records.append((record_type, host))

        if FQDN_RE.match(host):
          full_host_count += 1

    # Now that we've read everything, are we dealing with domains or full hostnames?
    full_host_percent = full_host_count / float(len(records)) * 100
    if full_host_percent < MAX_FQDN_SYNTHESIZE_PERCENT:
      full_host_names = False
    else:
      full_host_names = True

    return (records, full_host_names)

  def GetTestsFromSource(self, source, count=50, select_mode=None):
    """Parse records from source, and returnrequest tuples to use for testing.

    This is tricky because we support 3 types of input data:

    - List of domains
    - List of hosts
    - List of record_type + hosts
    """
    records = []

    # Convert entries into tuples, determine if we are using full hostnames
    full_host_count = 0
    www_host_count = 0
    (records, are_records_fqdn) = self._CreateRecordsFromHostEntries(self._GetHostsFromSource(source))

    # First try to resolve whether to use weighted or random.
    if select_mode in ('weighted', 'automatic', None):
      if len(records) != len(set(records)):
        if select_mode == 'weighted':
          self.msg('%s data contains duplicates, switching select_mode to random' % source)
        select_mode = 'random'
      else:
        select_mode = 'weighted'

    self.msg('Picking %s records from %s in %s mode' % (count, source, select_mode))
    # Now make the real selection.
    if select_mode == 'weighted':
      records = selectors.WeightedDistribution(records, count)
    elif select_mode == 'chunk':
      records = selectors.ChunkSelect(records, count)
    elif select_mode == 'random':
      records = selectors.RandomSelect(records, count)

    if are_records_fqdn:
      self.msg('%s input appears to be predominantly domain names. Synthesizing FQDNs' % source)
      synthesized = []
      for (req_type, hostname) in records:
        if not FQDN_RE.match(hostname):
          hostname = self._GenerateRandomHostname(hostname)
        synthesized.append((req_type, hostname))
      return synthesized
    else:
      return records

  def _GenerateRandomHostname(self, domain):
    """Generate a random hostname f or a given domain."""
    oracle = random.randint(0, 100)
    if oracle < 70:
      return 'www.%s' % domain
    elif oracle < 95:
      return domain
    elif oracle < 98:
      return 'static.%s' % domain
    else:
      return 'cache-%s.%s' % (random.randint(0, 10), domain)

  def _GetHostsFromSource(self, source, min_file_size=None, max_mtime_age_days=None):
    """Get data for a particular source. This needs to be fast.

    We support 3 styles of files:

    * One-per line list in form of record-type: host
    * One-per line list of unique domains
    * Any form with URL's.

    The results of this function get cached.
    """
    if source in self.source_cache:
      return self.source_cache[source]
    filename = self._FindBestFileForSource(source, min_file_size=min_file_size,
                                           max_mtime_age_days=max_mtime_age_days)
    if not filename:
      return None

    size_mb = os.path.getsize(filename) / 1024.0 / 1024.0
    self.msg('Reading %s: %s (%0.1fMB)' % (self.GetNameForSource(source), filename, size_mb))
    start_clock = DEFAULT_TIMER()
    hosts = self._ExtractHostsFromHistoryFile(filename)
    if not hosts:
      hosts = self._ReadDataFile(filename)
    duration = DEFAULT_TIMER() - start_clock
    if duration > 5:
      self.msg('%s data took %1.1fs to read!' % (self.GetNameForSource(source), duration))
    self.source_cache[source] = hosts
    return hosts

  def _ExtractHostsFromHistoryFile(self, path):
    """Get a list of sanitized records from a history file containing URLs."""
    # This regexp is fairly general (no ip filtering), since we need speed more
    # than precision at this stage.
    parse_re = re.compile('https*://([\-\w]+\.[\-\w\.]+)')
    return parse_re.findall(open(path, 'rb').read())

  def _ReadDataFile(self, path):
    """Read a line-based datafile."""
    records = []
    for line in open(path).readlines():
      if not line.startswith('#'):
        records.append(line.rstrip())
    return records

  def _GetSourceSearchPaths(self, source):
    """Get a list of possible search paths (globs) for a given source."""
    
    # This is likely a custom file path
    if source not in self.source_config:
      return [source]

    search_paths = []
    environment_re = re.compile('%(\w+)%')


    # First get through resolving environment variables
    for path in self.source_config[source]['search_paths']:
      env_vars = set(environment_re.findall(path))
      if env_vars:
        for variable in env_vars:
          env_var = os.getenv(variable, False)
          if env_var:
            path = path.replace('%%%s%%' % variable, env_var)
          else:
            path = None

      # If everything is good, replace all '/'  chars with the os path variable.
      if path:
        path = path.replace('/', os.sep)
        search_paths.append(path)

        # This moment of weirdness brought to you by Windows XP(tm). If we find
        # a Local or Roaming keyword in path, add the other forms to the search
        # path.
        if sys.platform[:3] == 'win':
          keywords = ('Local', 'Roaming')
          for keyword in keywords:
            if keyword in path:
              replacement = keywords[keywords.index(keyword)-1]
              search_paths.append(path.replace('\\%s' % keyword, '\\%s' % replacement))
              search_paths.append(path.replace('\\%s' % keyword, ''))

    return search_paths

  def _FindBestFileForSource(self, source, min_file_size=None,
                             max_mtime_age_days=None):
    """Find the best file (newest over X size) to use for a given source type.

    Args:
      source: source type

    Returns:
      A file path.
    """
    found = []
    for path in self._GetSourceSearchPaths(source):
      if not os.path.isabs(path):
        path = util.FindDataFile(path)

      for filename in glob.glob(path):
        if min_file_size and os.path.getsize(filename) < min_file_size:
          self.msg('Ignoring %s (only %s bytes)' % (filename, os.path.getsize(filename)))
        else:
          found.append(filename)

    if found:
      newest = sorted(found, key=os.path.getmtime)[-1]
      age_days = (time.time() - os.path.getmtime(newest)) / 86400
      if max_mtime_age_days and age_days > max_mtime_age_days:
        self.msg('Ignoring %s from %s (%2.0f days old)' % (newest, source, age_days))
      else:
        return newest
    else:
      return None

if __name__ == '__main__':
  parser = DataSources()
  print parser.ListSourceTypes()
  print parser.ListSourcesWithDetails()
  best = parser.ListSourcesWithDetails()[0][0]
  print len(parser.GetRecordsFromSource(best))
