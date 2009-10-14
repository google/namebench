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
import os.path
import re
import sys


class HistoryParser(object):
  """Parse the history file from files and web browsers and such."""

  MAX_NON_UNIQUE_RECORD_COUNT = 500000
  MIN_FILE_SIZE = 128
  MIN_RECOMMENDED_RECORD_COUNT = 2
  INTERNAL_RE = re.compile('\.prod|\.corp|\.bor|internal|dmz')
  TYPES = {}

  def __init__(self):
    self.TYPES = {
        'chrome': ('Google Chrome', self.GoogleChromeHistoryPath),
        'chromium': ('Chromium', self.ChromiumHistoryPath),
        'epiphany': ('Epiphany', self.EpiphanyHistoryPath),
        'opera': ('Opera', self.OperaHistoryPath),
        'safari': ('Apple Safari', self.SafariHistoryPath),
        'firefox': ('Mozilla Firefox', self.FirefoxHistoryPath),
        'internet_explorer': ('Microsoft Internet Explorer', self.InternetExplorerHistoryPath),
        'squid': ('Squid Web Proxy', self.SquidLogPath),
    }

  def GetTypes(self):
    """Return a tuple of type names with a description."""
    return dict([(x, self.TYPES[x][0]) for x in self.TYPES])

  def GetTypeMethod(self, type):
    return self.TYPES[type][1]

  def Parse(self, path_or_type):
    if path_or_type == 'auto':
      # TODO(tstromberg): complete this method
      all = self.ParseAllTypes()

    if path_or_type.lower() in self.TYPES:
      return self.ParseByType(path_or_type.lower())
    else:
      return self.ParseByFilename(path_or_type)

  def ParseByType(self, source, complain=False):
    """Given a type, parse the newest file and return a list of hosts."""
    (paths, tried) = self.FindGlobPaths(self.GetTypeMethod(source)())
    if not paths:
      if complain:
        print "* Could not find data for '%s'. Tried:"
        for path in tried:
          print path
      return None
    newest = sorted(paths, key=os.path.getmtime)[-1]
    return self.ParseByFilename(newest)

  def ParseAllTypes(self):
    """For each type we know of, attempt to find and parse each of them.

    Returns:
      dict of type: list of hosts
    """
    results = {}

    for type in self.GetTypes():
      hosts = self.ParseByType(type)
      if hosts and len(hosts) >= self.MIN_RECOMMENDED_RECORD_COUNT:
        results[type] = hosts
    return results

  def ParseByFilename(self, filename):
    # Only matches http://host.domain type entries (needs at least one subdom)
    parse_re = re.compile('\w+://([\-\w]+\.[\-\w\.]+)')
    print '- Reading history from %s' % filename
    # binary mode is necessary for running under Windows
    return parse_re.findall(open(filename, 'rb').read())

  def GenerateTestDataFromInput(self, path_or_type):
    hosts = self.Parse(path_or_type)
    if len(hosts) > self.MAX_NON_UNIQUE_RECORD_COUNT:
      sorted_unique = True
    else:
      sorted_unique = False
    return self.GenerateTestData(hosts, sorted_unique=sorted_unique)

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

      if self.INTERNAL_RE.search(host):
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

  def FindGlobPaths(self, paths):
    """Given a list of glob paths, return a list of matches containing data.

    Returns:
      A tuple with (file path (str), list of paths checked)
    """
    tried = []
    found = []
    for path_elements in paths:
      path = os.path.join(*path_elements)
      tried.append(path)
      for filename in glob.glob(path):
        if os.path.getsize(filename) > self.MIN_FILE_SIZE:
          found.append(filename)

    return (found, tried)

  def GoogleChromeHistoryPath(self):
    paths = (
        (os.getenv('HOME', ''), 'Library', 'Application Support', 'Google',
         'Chrome', 'Default', 'History'),
        (os.getenv('HOME', ''), '.config', 'google-chrome', 'Default',
         'History'),
        (os.getenv('APPDATA', ''), 'Google', 'Chrome', 'User Data', 'Default',
         'History'),
        (os.getenv('USERPROFILE', ''), 'Local Settings', 'Application Data',
         'Google', 'Chrome', 'User Data', 'Default', 'History'),
    )
    return paths

  def ChromiumHistoryPath(self):
    """It's like Chrome, but with the branding stripped out."""

    # TODO(tstromberg): Find a terser way to do this.
    paths = []
    for path in self.GoogleChromeHistoryPath():
      new_path = list(path)
      if 'Google' in new_path:
        new_path.remove('Google')
      for (index, part) in enumerate(new_path):
        if part == 'Chrome':
          new_path[index] = 'Chromium'
        elif part == 'chrome':
          new_path[index] = 'chromium'
      paths.append(new_path)
    return paths

  def OperaHistoryPath(self):
    paths = (
        (os.getenv('HOME', ''), 'Library', 'Preferences', 'Opera Preferences',
         'global_history.dat'),
    )
    return paths

  def SafariHistoryPath(self):
    paths = (
        (os.getenv('HOME', ''), 'Library', 'Safari', 'History.plist'),
        (os.getenv('APPDATA', ''), 'Apple Computer', 'Safari',
         'History.plist')
    )
    return paths

  def FirefoxHistoryPath(self):
    paths = (
        (os.getenv('HOME', ''), 'Library', 'Application Support', 'Firefox',
         'Profiles', '*', 'places.sqlite'),
        (os.getenv('HOME', ''), '.mozilla', 'firefox', '*', 'places.sqlite'),
        (os.getenv('APPDATA', ''), 'Mozilla', 'Firefox', 'Profiles', '*',
         'places.sqlite')
    )
    return paths

  def InternetExplorerHistoryPath(self):
    paths = (
        # XP
        (os.getenv('USERPROFILE', ''), 'Local Settings', 'History',
         'History.IE5', 'index.dat'),
        # ?
        (os.getenv('APPDATA', ''), 'Microsoft', 'Windows', 'History',
         'History.IE5', 'index.dat'),
    )
    return paths

  def EpiphanyHistoryPath(self):
    paths = (
        (os.getenv('HOME', ''), '.gnome2', 'epiphany', 'ephy-history.xml'),
    )
    return paths

  def SquidLogPath(self):
    paths = (
        ('/usr/local/squid/logs/access.log',),
        ('/var/log/squid/access_log',)
    )
    return paths

if __name__ == '__main__':
  parser = HistoryParser()
  types_str = ', '.join(parser.TYPES.keys())
  if len(sys.argv) < 2:
    print 'You must provide a filename or history file type (%s)' % types_str
    sys.exit(1)

  records = parser.Parse(sys.argv[1])
  for record in records:
    print record

