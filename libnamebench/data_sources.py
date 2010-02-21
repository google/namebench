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
import operator
import os
import os.path
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
import util

GLOBAL_DATA_CACHE = {}
INTERNAL_RE = re.compile('^0|\.pro[md]|\.corp|\.bor|internal|dmz|intra')
IP_RE = re.compile('^[0-9.]$')
DEFAULT_CONFIG_PATH = "config/data_sources.cfg"
MAX_NON_UNIQUE_RECORD_COUNT = 500000
MAX_FILE_MTIME_AGE_DAYS = 60
MIN_FILE_SIZE = 10000
MIN_RECOMMENDED_RECORD_COUNT = 200

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
    return self.source_config.keys()

  def ListSourcesWithDetails(self):
    """Get a list of all data sources found with total counts.

    Returns:
      List of tuples in form of (short_name, full_name, full_hosts, # of entries)
    """
    for source in self.ListSourceTypes():
      self._GetHostsFromSource(source)

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

  def GetRecordsFromSource(self, source):
    """Parse records from source, and returnrequest tuples to use for testing.

    This is tricky because we support 3 types of input data:

    - List of domains
    - List of hosts
    - List of record_type + hosts
    """
    records = []
    real_tld_re = re.compile('[a-z]{2,4}$')
    internal_re = re.compile('')
    last_hostname = None

    entries = self._GetHostsFromSource(source)

    # First a quick check to see if our input source is strictly domains or hosts.
    full_hostnames = False
    for entry in entries:
      if entry.startswith('www.') or entry.startswith('smtp.'):
        full_hostnames = True
        break
    
    for entry in entries:
      record_type = 'A'
      if ' ' in entry:
        (record_type, hostname) = entry.split(' ')
      elif not full_hostnames:
        hostname = self.GenerateRandomHostnameForDomain(host)
      else:
        if entry == last_hostname:
          continue
        hostname = entry
        last_hostname = entry

        # Throw out the things we shouldn't be testing.
        if IP_RE.match(hostname) or INTERNAL_RE.search(hostname) or hostname.endswith('.local'):
          continue

      # Make sure to add the trailing dot.
      if not hostname.endswith('.'):
        hostname = '%s.' % hostname
      records.append((record_type, '%s.' % hostname))
    return records

  def _GenerateRandomHostnameForDomain(self, domain):
    oracle = random.randint(0, 100)
    if oracle < 60:
      return 'www.%s.' % domain
    elif oracle < 95:
      return '%s.' % domain
    elif oracle < 98:
      return 'static.%s.' % domain
    else:
      return 'cache-%s.%s.' % (random.randint(0, 10), domain)

  def _GetHostsFromSource(self, source):
    """Get data for a particular source. This is a bit tricky.

    We support 3 styles of files:

    * One-per line list in form of record-type: host
    * One-per line list of unique domains
    * Any form with URL's.
    """
    filename = self._FindBestFileForSource(source)
    if not filename:
      return None

    if source in self.source_cache:
      return self.source_cache[source]

    size_mb = os.path.getsize(filename) / 1024.0 / 1024.0
    self.msg('Reading %s (%0.1fMB)' % (filename, size_mb))
    hosts = self._ExtractHostsFromHistoryFile(filename)
    if not hosts:
      hosts = self._ReadDataFile(filename)
  
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
        records.append(line.rstrip)
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

  def _FindBestFileForSource(self, source, min_file_size=MIN_FILE_SIZE,
                             max_mtime_age_days=MAX_FILE_MTIME_AGE_DAYS):
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
        if os.path.getsize(filename) < min_file_size:
          self.msg('Ignoring %s (only %s bytes)' % (filename, os.path.getsize(filename)))
        else:
          found.append(filename)

    if found:
      newest = sorted(found, key=os.path.getmtime)[-1]
      age_days = (time.time() - os.path.getmtime(newest)) / 86400
      if age_days > max_mtime_age_days:
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
