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

import ConfigParser
import glob
import os
import os.path
import random
import re
import subprocess
import sys
import time

# relative
import addr_util
import selectors
import util

# Pick the most accurate timer for a platform. Stolen from timeit.py:
if sys.platform[:3] == 'win':
  DEFAULT_TIMER = time.clock
else:
  DEFAULT_TIMER = time.time

GLOBAL_DATA_CACHE = {}

DEFAULT_CONFIG_PATH = 'config/data_sources.cfg'
MAX_NON_UNIQUE_RECORD_COUNT = 500000
MAX_FILE_MTIME_AGE_DAYS = 45
MIN_FILE_SIZE = 10000
MIN_RECOMMENDED_RECORD_COUNT = 200
MAX_FQDN_SYNTHESIZE_PERCENT = 4


class DataSources(object):
  """A collection of methods related to available hostname data sources."""

  def __init__(self, config_path=DEFAULT_CONFIG_PATH, status_callback=None):
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
    """Load a configuration file describing data sources that may be available."""
    conf_file = util.FindDataFile(path)
    config = ConfigParser.ConfigParser()
    config.read(conf_file)
    for section in config.sections():
      if section not in self.source_config:
        self.source_config[section] = {
            'name': None,
            'search_paths': set(),
            'full_hostnames': True,
            # Store whether or not this data source contains personal data
            'synthetic': False,
            'include_duplicates': False,
            'max_mtime_days': MAX_FILE_MTIME_AGE_DAYS
        }

      for (key, value) in config.items(section):
        if key == 'name':
          self.source_config[section]['name'] = value
        elif key == 'full_hostnames' and int(value) == 0:
          self.source_config[section]['full_hostnames'] = False
        elif key == 'max_mtime_days':
          self.source_config[section]['max_mtime_days'] = int(value)
        elif key == 'include_duplicates':
          self.source_config[section]['include_duplicates'] = bool(value)
        elif key == 'synthetic':
          self.source_config[section]['synthetic'] = bool(value)
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
      max_mtime = self.source_config[source]['max_mtime_days']
      self._GetHostsFromSource(source, min_file_size=MIN_FILE_SIZE,
                               max_mtime_age_days=max_mtime)

    details = []
    for source in self.source_cache:
      details.append((source,
                      self.source_config[source]['name'],
                      self.source_config[source]['synthetic'],
                      len(self.source_cache[source])))
    return sorted(details, key=lambda x: (x[2], x[3] * -1))

  def ListSourceTitles(self):
    """Return a list of sources in title + count format."""
    titles = []
    seen_synthetic = False
    seen_organic = False
    for (unused_type, name, is_synthetic, count) in self.ListSourcesWithDetails():
      if not is_synthetic:
        seen_organic = True

      if is_synthetic and seen_organic and not seen_synthetic:
        titles.append('-' * 36)
        seen_synthetic = True
      titles.append('%s (%s)' % (name, count))
    return titles

  def ConvertSourceTitleToType(self, detail):
    """Convert a detail name to a source type."""
    for source_type in self.source_config:
      if detail.startswith(self.source_config[source_type]['name']):
        return source_type

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

  def _CreateRecordsFromHostEntries(self, entries, include_duplicates=False):
    """Create records from hosts, removing duplicate entries and IP's.

    Args:
      entries: A list of test-data entries.
      include_duplicates: Whether or not to filter duplicates (optional: False)

    Returns:
      A tuple of (filtered records, full_host_names (Boolean)

    Raises:
      ValueError: If no records could be grokked from the input.
    """
    last_entry = None

    records = []
    full_host_count = 0
    for entry in entries:
      if entry == last_entry and not include_duplicates:
        continue
      else:
        last_entry = entry

      if ' ' in entry:
        (record_type, host) = entry.split(' ')
      else:
        record_type = 'A'
        host = entry

      if not addr_util.IP_RE.match(host) and not addr_util.INTERNAL_RE.search(host):
        if not host.endswith('.'):
          host += '.'
        records.append((record_type, host))

        if addr_util.FQDN_RE.match(host):
          full_host_count += 1

    if not records:
      raise ValueError('No records could be created from: %s' % entries)

    # Now that we've read everything, are we dealing with domains or full hostnames?
    full_host_percent = full_host_count / float(len(records)) * 100
    if full_host_percent < MAX_FQDN_SYNTHESIZE_PERCENT:
      full_host_names = True
    else:
      full_host_names = False
    return (records, full_host_names)

  def GetTestsFromSource(self, source, count=50, select_mode=None):
    """Parse records from source, and return tuples to use for testing.

    Args:
      source: A source name (str) that has been configured.
      count: Number of tests to generate from the source (int)
      select_mode: automatic, weighted, random, chunk (str)

    Returns:
      A list of record tuples in the form of (req_type, hostname)

    Raises:
      ValueError: If no usable records are found from the data source.

    This is tricky because we support 3 types of input data:

    - List of domains
    - List of hosts
    - List of record_type + hosts
    """
    records = []

    if source in self.source_config:
      include_duplicates = self.source_config[source].get('include_duplicates', False)
    else:
      include_duplicates = False

    records = self._GetHostsFromSource(source)
    if not records:
      raise ValueError('Unable to generate records from %s (nothing found)' % source)

    self.msg('Generating tests from %s (%s records, selecting %s %s)'
             % (self.GetNameForSource(source), len(records), count, select_mode))
    (records, are_records_fqdn) = self._CreateRecordsFromHostEntries(records,
                                                                     include_duplicates=include_duplicates)
    # First try to resolve whether to use weighted or random.
    if select_mode in ('weighted', 'automatic', None):
      # If we are in include_duplicates mode (cachemiss, cachehit, etc.), we have different rules.
      if include_duplicates:
        if count > len(records):
          select_mode = 'random'
        else:
          select_mode = 'chunk'
      elif len(records) != len(set(records)):
        if select_mode == 'weighted':
          self.msg('%s data contains duplicates, switching select_mode to random' % source)
        select_mode = 'random'
      else:
        select_mode = 'weighted'

    self.msg('Selecting %s out of %s sanitized records (%s mode).' %
             (count, len(records), select_mode))
    if select_mode == 'weighted':
      records = selectors.WeightedDistribution(records, count)
    elif select_mode == 'chunk':
      records = selectors.ChunkSelect(records, count)
    elif select_mode == 'random':
      records = selectors.RandomSelect(records, count, include_duplicates=include_duplicates)
    else:
      raise ValueError('No such final selection mode: %s' % select_mode)

    # For custom filenames
    if source not in self.source_config:
      self.source_config[source] = {'synthetic': True}

    if are_records_fqdn:
      self.source_config[source]['full_hostnames'] = False
      self.msg('%s input appears to be predominantly domain names. Synthesizing FQDNs' % source)
      synthesized = []
      for (req_type, hostname) in records:
        if not addr_util.FQDN_RE.match(hostname):
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

    Args:
      source: A configured source type (str)
      min_file_size: What the minimum allowable file size is for this source (int)
      max_mtime_age_days: Maximum days old the file can be for this source (int)

    Returns:
      list of hostnames gathered from data source.

    The results of this function are cached by source type.
    """
    if source in self.source_cache:
      return self.source_cache[source]
    filename = self._FindBestFileForSource(source, min_file_size=min_file_size,
                                           max_mtime_age_days=max_mtime_age_days)
    if not filename:
      return None

    size_mb = os.path.getsize(filename) / 1024.0 / 1024.0
    # Minimize our output
    if not self.source_config[source]['synthetic']:
      self.msg('Reading %s: %s (%0.1fMB)' % (self.GetNameForSource(source), filename, size_mb))
    start_clock = DEFAULT_TIMER()
    if filename.endswith('.pcap') or filename.endswith('.tcp'):
      hosts = self._ExtractHostsFromPcapFile(filename)
    else:
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

  def _ExtractHostsFromPcapFile(self, path):
    """Get a list of requests out of a pcap file - requires tcpdump."""
    self.msg('Extracting requests from pcap file using tcpdump')
    cmd = 'tcpdump -r %s -n port 53' % path
    pipe = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).stdout
    parse_re = re.compile(' ([A-Z]+)\? ([\-\w\.]+)')
    requests = []
    for line in pipe:
      if '?' not in line:
        continue
      match = parse_re.search(line)
      if match:
        requests.append(' '.join(match.groups()))
    return requests

  def _ReadDataFile(self, path):
    """Read a line-based datafile."""
    records = []
    domains_re = re.compile('^\w[\w\.-]+[a-zA-Z]$')
    requests_re = re.compile('^[A-Z]{1,4} \w[\w\.-]+\.$')
    for line in open(path):
      if domains_re.match(line) or requests_re.match(line):
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
          keywords = ['Local', 'Roaming']
          for keyword in keywords:
            if keyword in path:
              replacement = keywords[keywords.index(keyword)-1]
              search_paths.append(path.replace('\\%s' % keyword, '\\%s' % replacement))
              search_paths.append(path.replace('\\%s' % keyword, ''))

    return search_paths

  def _FindBestFileForSource(self, source, min_file_size=None, max_mtime_age_days=None):
    """Find the best file (newest over X size) to use for a given source type.

    Args:
      source: source type
      min_file_size: What the minimum allowable file size is for this source (int)
      max_mtime_age_days: Maximum days old the file can be for this source (int)

    Returns:
      A file path.
    """
    found = []
    for path in self._GetSourceSearchPaths(source):
      if not os.path.isabs(path):
        path = util.FindDataFile(path)

      for filename in glob.glob(path):
        if min_file_size and os.path.getsize(filename) < min_file_size:
          self.msg('Skipping %s (only %sb)' % (filename, os.path.getsize(filename)))
        else:
          try:
            fp = open(filename, 'rb')
            fp.close()
            found.append(filename)
          except IOError:
            self.msg('Skipping %s (could not open)' % filename)

    if found:
      newest = sorted(found, key=os.path.getmtime)[-1]
      age_days = (time.time() - os.path.getmtime(newest)) / 86400
      if max_mtime_age_days and age_days > max_mtime_age_days:
        pass
#        self.msg('Skipping %s (%2.0fd old)' % (newest, age_days))
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
