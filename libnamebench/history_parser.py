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
import time
import threading

def sourceToTitle(source):
  """Convert a source tuple to a title."""
  (short_name, full_name, num_hosts) = source
  return '%s (%s)' % (full_name, num_hosts)

class ParserThread(threading.Thread):
  def __init__(self, record_type):
    threading.Thread.__init__(self)
    self.type = record_type

  def run(self):
    hp = HistoryParser()
    self.hosts = hp.ParseByType(self.type)
    return self.hosts

class HistoryParser(object):
  """Parse the history file from files and web browsers and such."""

  MAX_NON_UNIQUE_RECORD_COUNT = 500000
  MIN_FILE_SIZE = 128
  MIN_RECOMMENDED_RECORD_COUNT = 2
  INTERNAL_RE = re.compile('\.prod|\.corp|\.bor|internal|dmz')
  IP_RE = re.compile('^[\d\.]+$')
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
        'konqueror': ('Konqueror', self.KonquerorHistoryPath),
        'seamonkey': ('Mozilla Seamonkey', self.SeamonkeyHistoryPath),
        'squid': ('Squid Web Proxy', self.SquidLogPath),
    }

  def GetTypes(self):
    """Return a tuple of type names with a description."""
    return dict([(x, self.TYPES[x][0]) for x in self.TYPES])

  def GetParsedSource(self, type):
    return self.imported_sources[type]

  def GetAvailableHistorySources(self):
    """Seek out and create a list of valid data sources.

    Returns:
      sources: A list of tuples (type, description, record count)
    """
    source_desc = self.GetTypes()
    self.imported_sources = self.ParseAllTypes()
    sources = []
    for src_type in self.imported_sources:
      sources.append(
        (src_type, source_desc[src_type], len(self.imported_sources[src_type]))
      )
    sources.sort(key=operator.itemgetter(2), reverse=True)
    # TODO(tstromberg): Don't hardcode input types.
    sources.append((None, 'Alexa Top Global Domains', 10000))
    return sources

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

  def ParseByType(self, source, complain=True):
    """Given a type, parse the newest file and return a list of hosts."""

    (paths, tried) = self.FindGlobPaths(self.GetTypeMethod(source)())
    if not paths:
      if complain:
        print "- %s: no matches in %s" % (source, tried)
      return False
    newest = sorted(paths, key=os.path.getmtime)[-1]
    return self.ParseByFilename(newest)

  def ParseAllTypes(self):
    """For each type we know of, attempt to find and parse each of them.

    Returns:
      dict of type: list of hosts
    """
    start_time = time.time()
    results = {}
    records = 0
    threads = []

    for type in self.GetTypes():
      thread = ParserThread(type)
      thread.start()
      threads.append(thread)

    for thread in threads:
      thread.join()
      if thread.hosts:
        records += len(thread.hosts)

      if thread.hosts and len(thread.hosts) >= self.MIN_RECOMMENDED_RECORD_COUNT:
        results[thread.type] = thread.hosts
        print "- Found %s records from %s" % (len(thread.hosts), thread.type)
      elif thread.hosts == False:
        pass
      elif not thread.hosts:
        print '- No records found in %s' % (thread.type)
      else:
        print '- Ignoring %s (only %s records)' % (thread.type, len(thread.hosts))

    print '- Read %s records from %s in %ss' % (records, ', '.join(results.keys()), time.time() - start_time)
    return results

  def ParseByFilename(self, filename):
    # Only matches http://host.domain type entries (needs at least one subdom)
    parse_re = re.compile('\w+://([\-\w]+\.[\-\w\.]+)')
    print '* Reading %s' % filename
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
        
      if self.IP_RE.match(host):
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
        else:
          print "* %s exists, but is only %s bytes" % (filename, os.path.getsize(filename))

    return (found, tried)

  def GoogleChromeHistoryPath(self):
    paths = (
        (os.getenv('HOME', ''), 'Library', 'Application Support', 'Google',
         'Chrome', 'Default', 'History'),
        (os.getenv('HOME', ''), '.config', 'google-chrome', 'Default',
         'History'),
        (os.getenv('APPDATA', ''), 'Google', 'Chrome', 'User Data', 'Default',
         'History'),
        (os.getenv('APPDATA', ''), 'Local', 'Google', 'Chrome', 'User Data',
         'Default', 'History'),
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
        elif part == 'chrome' or part == 'google-chrome':
          new_path[index] = 'chromium'
      paths.append(new_path)
      
    return paths

  def OperaHistoryPath(self):
    paths = (
        (os.getenv('HOME', ''), 'Library', 'Preferences', 'Opera Preferences',
         'global_history.dat'),
        (os.getenv('HOME', ''), 'Library', 'Preferences', 'Opera Preferences 10',
         'global_history.dat'),
        (os.getenv('APPDATA', ''), 'Opera', 'Opera', 'global_history.dat'),
        (os.getenv('APPDATA', ''), 'Local', 'Opera', 'Opera', 'global_history.dat'),
        (os.getenv('HOME', ''), '.opera', 'global_history.dat'),
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

  def SeamonkeyHistoryPath(self):
    paths = (
        (os.getenv('HOME', ''), 'Library', 'Application Support', 'Seamonkey',
         'Profiles', '*', 'history.dat'),
        (os.getenv('HOME', ''), '.mozilla', 'seamonkey', '*', 'history.dat'),
        (os.getenv('HOME', ''), '.mozilla', 'default', '*', 'history.dat'),
        (os.getenv('APPDATA', ''), 'Mozilla', 'Seamonkey', 'Profiles', '*',
         'history.dat')
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

  def KonquerorHistoryPath(self):
    paths = (
        (os.getenv('HOME', ''), '.kde4', 'share',  'apps', 'konqueror', 'konq_history'),
        (os.getenv('HOME', ''), '.kde', 'share',  'apps', 'konqueror', 'konq_history'),
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

