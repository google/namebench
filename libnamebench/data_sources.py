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
import ConfigParser

# See if a third_party library exists -- use it if so.
try:
  import third_party
except ImportError:
  pass


# relative
import util

INTERNAL_RE = re.compile('\.prod|\.corp|\.bor|internal|dmz|intranet')
DEFAULT_CONFIG_PATH = "config/data_sources.cfg"
MAX_NON_UNIQUE_RECORD_COUNT = 500000
MIN_FILE_SIZE = 10000
MIN_RECOMMENDED_RECORD_COUNT = 200

class DataSources(object):
  def __init__(self, config_path=DEFAULT_CONFIG_PATH, status_callback=None):
    self.source_cache = {}
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
        self.source_config[section] = {'name': 'Unknown', 'search_paths': set()}

      for (key, value) in config.items(section):
        if key == 'name':
          self.source_config[section]['name'] = value
        else:
          self.source_config[section]['search_paths'].add(value)

  def ListSourceTypes(self):
    """Get a list of all data sources we know about."""
    return self.source_config.keys()

  def _GetSourceName(self, source):
    return self.source_config[source]['name']

  def ListSourcesWithDetails(self):
    """Get a list of all data sources found with total counts."""
    for source in self.ListSourceTypes():
      self._GetRecordsForSource(source)

    details = []
    for source in self.source_cache:
      details.append((source, self.GetSourceName(source), len(self.source_cache[source])))
    return details

  def _GetRecordsForSource(self, source):
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
    records = self._GetRecordsFromHistoryFile(filename)
    if records:
      print len(records)

  def _GetRecordsFromHistoryFile(self, path):
    """Get a list of sanitized records from a history file containing URLs."""

    # Only pull out URL's with at leats two dots, including an letter.
    parse_re = re.compile('https*://([\-\w]+\.[\-\w\.]+[a-zA-Z]+)')
    records = []
    for hostname in parse_re.findall(open(path, 'rb').read()):
      if not INTERNAL_RE.search(hostname):
        records.append(('A', hostname))
    return records

  def _GetSourceSearchPaths(self, source):
    """Get a list of possible search paths (globs) for a given source."""
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

    return search_paths

  def _FindBestFileForSource(self, source, min_file_size=MIN_FILE_SIZE):
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
        if os.path.getsize(filename) > min_file_size:
          found.append(filename)
        else:
          self.msg('Ignoring %s (only %s bytes)' % (filename, os.path.getsize(filename)))

    if found:
      return sorted(found, key=os.path.getmtime)[-1]
    else:
      return None

  def _AddRoamLocalWindowsPaths(self, paths):
    """Windows path munging: Add neutered and swapped paths for Local/roaming dirs."""
    keywords = ('Local', 'Roaming')
    new_paths = list(paths)
    for path in paths:
      for keyword in keywords:
        if path[0] and keyword in path[0]:
          swapped_path = list(path)
          neutered_path = list(path)

          replacement = keywords[keywords.index(keyword)-1]

          swapped_path[0] = swapped_path[0].replace('\\%s' % keyword, '\\%s' % replacement)
          neutered_path[0] = neutered_path[0].replace('\\%s' % keyword, '')
          new_paths.extend([swapped_path, neutered_path])
    return new_paths

if __name__ == '__main__':
  parser = DataSources()
  print parser.ListSourceTypes()
  print parser.ListSourcesWithDetails()

