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

"""Parse the history file for just about anything."""
import glob
import operator
import os
import re
import sys


class HistoryParser(object):
  """Parse the history file from files and web browsers and such."""

  # At 32MB, switch from replay format to sorted_unique
  MAX_REPLAY_SIZE = 33554432
  INTERNAL_RE = re.compile('\.prod|\.corp|\.bor|internal|dmz')
  TYPES = {}

  def __init__(self):
    self.TYPES = {
        'google_chrome': self.GoogleChromeHistoryPath,
        'chrome': self.GoogleChromeHistoryPath,
        'opera': self.OperaHistoryPath,
        'safari': self.SafariHistoryPath,
        'firefox': self.FirefoxHistoryPath,
        'internet_explorer': self.InternetExplorerHistoryPath,
        'iexplorer': self.InternetExplorerHistoryPath,
        'ie': self.InternetExplorerHistoryPath,
        'squid': self.SquidLogPath
    }

  def Parse(self, path_or_type):
    if path_or_type.lower() in self.TYPES:
      return self.ParseByType(path_or_type.lower())
    else:
      return self.ParseByFilename(path_or_type)

  def ReadHistoryFile(self, filename):
    # Only matches http://host.domain type entries (needs at least one sub)
    parse_re = re.compile('\w+://([\-\w]+\.[\-\w\.]+)')
    return parse_re.findall(open(filename).read())

  def _HostnameMayBeInternal(self, hostname):
    if self.INTERNAL_RE.search(hostname):
      return True

  def GenerateTestData(self, hosts, sorted_unique=False):
    """Given a set of hosts, generate test data.

    Args:
      hosts: A list of hostnames
      sorted_unique: Return a sorted unique list of tests. Useful for large
                     data sets.

    Returns:
      A list of strings representing DNS requests to test with.
    """
    history = []
    hits = {}
    last_host = None

    for host in hosts:
      if not host.endswith('.'):
        host = host + '.'
      
      if self._HostnameMayBeInternal(host):
        continue

      if host != last_host:
        if sorted_unique:
          hits[host] = hits.get(host, 0) + 1
        else:
          history.append('A %s' % host)
        last_host = host

    if sorted_unique:
      for (hit, count) in sorted(hits.items(), key=operator.itemgetter(1),
                                 reverse=True):
        history.append('A %s # %s hits' % (hit, count))
    return history

  def ParseByFilename(self, filename):
    """Parse a history file, returning a history.

    Args:
      filename: duh

    Returns:
      a list of hosts

    If the filename passed is greater than MAX_REPLAY_SIZE, we return a
    unique list of hosts, sorted by descending popularity. If there are
    multiple subsequent records for a host, only the first one is parsed.
    """
    if os.path.getsize(filename) > self.MAX_REPLAY_SIZE:
      sorted_unique = True
    else:
      sorted_unique = False
    return self.GenerateTestData(self.ReadHistoryFile(filename),
                                 sorted_unique=sorted_unique)

  def ParseByType(self, source):
    (history_file_path, tried) = self.TYPES[source]()
    if not history_file_path:
      print "* Could not find data for '%s'. Tried: %s" % (source, tried)
      return None
    return self.ParseByFilename(history_file_path)

  def FindGlobPath(self, paths):
    """Given a list of glob paths, return the first one with a real file.

    Returns:
      A tuple with (file path (str), list of paths checked)
    """
    tried = []
    for path_elements in paths:
      path = os.path.join(*path_elements)
      tried.append(path)
      for filename in glob.glob(path):
        if os.path.getsize(filename) > 0:
          return (filename, tried)

    return (None, tried)

  def GoogleChromeHistoryPath(self):
    paths = (
        (os.getenv('HOME', None), 'Library', 'Application Support', 'Google',
         'Chrome', 'Default', 'History'),
        (os.getenv('HOME', None), '.config', 'google-chrome', 'Default',
         'History'),
        (os.getenv('APPDATA', None), 'Google', 'Chrome', 'Default',
         'History')
    )
    return self.FindGlobPath(paths)

  def OperaHistoryPath(self):
    paths = (
        (os.getenv('HOME', None), 'Library', 'Preferences', 'Opera Preferences',
         'global_history.dat'),
    )
    return self.FindGlobPath(paths)

  def SafariHistoryPath(self):
    paths = (
        (os.getenv('HOME', None), 'Library', 'Safari', 'History.plist'),
        (os.getenv('APPDATA', None), 'Apple Computer', 'Safari',
         'History.plist')
    )
    return self.FindGlobPath(paths)

  def FirefoxHistoryPath(self):
    paths = (
        (os.getenv('HOME', None), 'Library', 'Application Support', 'Firefox',
         'Profiles', '*', 'places.sqlite'),
        (os.getenv('APPDATA', None), 'Mozilla', 'Firefox', 'Profiles', '*',
         'places.sqlite')
    )
    return self.FindGlobPath(paths)

  def InternetExplorerHistoryPath(self):
    paths = (
        (os.getenv('APPDATA', None), 'Microsoft', 'Windows', 'History',
         'History.IE5', 'index.dat'),
    )
    return self.FindGlobPath(paths)

  def SquidLogPath(self):
    paths = (
        ('/usr/local/squid/logs/access.log',),
        ('/var/log/squid/access_log',)
    )
    return self.FindGlobPath(paths)

if __name__ == '__main__':
  parser = HistoryParser()
  types_str = ', '.join(parser.TYPES.keys())
  if len(sys.argv) < 2:
    print 'You must provide a filename or history file type (%s)' % types_str
    sys.exit(1)

  records = parser.Parse(sys.argv[1])
  for record in records:
    print record

