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

# At 32MB, switch from replay format to sorted_unique
MAX_REPLAY_SIZE = 33554432

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

  def ParseByFilename(self, filename, sorted_unique=False):
    """Parse a history file, returning a history.
    
    Args:
      filename: duh
      sorted_unique: Return unique list of hosts, ordered in popularity
    
    Returns:
      a list of hosts
    """
    # Only matches http://host.domain type entries (needs at least one sub)
    parse_re = re.compile('\w+://([\-\w]+\.[\-\w\.]+)')
    if sorted_unique:
      hits = {}
    else:
      history = []
    last_host = None

    matches = parse_re.findall(open(filename).read())
    for host in matches:
      if host != last_host:
        if sorted_unique:  
          hits[host] = hits.get(host, 0) + 1
        else:
          history.append(host)
        last_host = host

    if sorted_unique:
      print hits
      return sorted(hits.items(), key=operator.itemgetter(1), reverse=True)
    else:
      return history
    
  def ParseByType(self, type):
    return self.TYPES[type]()
    
  def ParseFirstPathHit(self, paths):
    tried = []
    for path_elements in paths:
      path = os.path.join(*path_elements)
      tried.append(path)
      for filename in glob.glob(path):
        if os.path.getsize(filename) > MAX_REPLAY_SIZE:
          sorted_unique = True
        else:
          sorted_unique = False
        return self.ParseByFilename(filename, sorted_unique=sorted_unique)
        
    print "Tried: %s" % tried
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
        ('/usr/local/squid/logs/access.log',),
        ('/var/log/squid/access_log',)
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
    history = parser.ParseByType(filename)
    if not history:
      print 'Unable to find the history file for %s' % filename
      sys.exit(3)

  elif os.path.exists(filename):
    history = parser.ParseByFilename(filename)
  else:
    print '%s is neither a file, nor in %s' % (filename, types_str)
    sys.exit(2)

  for host in history:
    print 'A %s.' % host

