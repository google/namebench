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
import operator
import glob
import os
import re
import sys

class HistoryParser(object):

  TYPES = {}
  
  def __init__(self):
    self.TYPES = {
        'google_chrome': self.GoogleChrome,
        'opera': self.Opera,
        'safari': self.Safari,
        'firefox': self.Firefox,
        'internet_explorer': self.InternetExplorer,
        'squid': self.Squid
    }

  def ParseByFilename(self, filename):
    # Only matches http://host.domain type entries (needs at least one sub)
    parse_re = re.compile('\w+://([\-\w]+\.[\-\w\.]+)')
    hits = {}
    last_host = None

    matches = parse_re.findall(open(filename).read())
    for host in matches:
      if host != last_host:
        hits[host] = hits.get(host, 0) + 1
        last_host = host
    return hits
    
  def ParseByType(self, type):
    return self.TYPES[type]()
    
  def ParseFirstPathHit(self, paths):
    for path_elements in paths:
      path = os.path.join(*path_elements)
      for filename in glob.glob(path):
        return self.ParseByFilename(filename)
    return False

  def GoogleChrome(self):
    paths = (
      (os.getenv('HOME', None), 'Library', 'Application Support', 'Google',
      'Chrome', 'Default', 'History'),
      (os.getenv('HOME', None), '.config', 'google-chrome', 'Default', 'History'),
      (os.getenv('APPDATA', None), 'Google', 'Chrome', 'Default',
      'History')
    )
    return self.ParseFirstPathHit(paths)
    
  def Opera(self):
    paths = (
      (os.getenv('HOME', None), 'Library', 'Preferences', 'Opera Preferences',
      'global_history.dat'),
    )
    return self.ParseFirstPathHit(paths)

  def Safari(self):
    paths = (
      (os.getenv('HOME', None), 'Library', 'Safari', 'History.plist'),
      (os.getenv('APPDATA', None), 'Apple Computer', 'Safari', 'History.plist')
    )
    return self.ParseFirstPathHit(paths)

  def Firefox(self):
    paths = (
      (os.getenv('HOME', None), 'Library', 'Application Support', 'Firefox',
      'Profiles', '*', 'places.sqlite'),
      (os.getenv('APPDATA', None), 'Mozilla', 'Firefox', 'Profiles', '*', 'places.sqlite')
    )
    return self.ParseFirstPathHit(paths)

  def InternetExplorer(self):
    paths = (
      (os.getenv('APPDATA', None), 'Microsoft', 'Windows', 'History', 'History.IE5',
      'index.dat'),
    )
    return self.ParseFirstPathHit(paths)
    
  def Squid(self):
    paths = (
        ('/usr/local/squid/logs/access_log'),
        ('/var/log/squid/access_log')
    )
    return self.ParseFirstPathHit(paths)
    
if __name__ == '__main__':
  parser = HistoryParser()
  types_str = ', '.join(parser.TYPES.keys())
  if len(sys.argv) < 2:
    print "You must provide a filename or history file type (%s)" % types_str
    sys.exit(1)

  filename = sys.argv[1]

  if filename in parser.TYPES:
    hits = parser.ParseByType(filename)
    if not hits:
      print 'Unable to find the history file for %s' % filename
      sys.exit(3)

  elif os.path.exists(filename):
    hits = parser.ParseByFilename(filename)
  else:
    print '%s is neither a file, nor in %s' % (filename, types_str)
    sys.exit(2)

  top_hits = sorted(hits.items(), key=operator.itemgetter(1),reverse=True)
  for (hit, count) in top_hits:
    print 'A %s.\t# %s hits' % (hit, count)

