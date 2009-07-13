#!/usr/bin/env python
# Copyright 2009 Google Inc. All Rights Reserved.

"""Simple DNS server comparison benchmarking tool.

Designed to assist system administrators in selection and prioritization.
"""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

VERSION='0.5'
print 'namebench %s' % VERSION
print '-' * 78

import os.path
import optparse
import operator
import pickle
import sys
import tempfile
import threading
import webbrowser
import ConfigParser

# Make it easy to import 3rd party utilities without editing their imports.
sys.path.append('lib/third_party')
from lib import nslookup
from lib import benchmark
from lib import web

SECONDARY_NS_CACHE = tempfile.gettempdir() + '/namebench_cache'

TEXT_WEB_BROWSERS = ('links', 'elinks', 'w3m', 'lynx')
DEFAULT_URL = 'http://127.0.0.1:8080'
SECONDARY_COUNT = 3

class WebServerThread (threading.Thread):
  def run(self):
    web.start()

def OpenBrowserWindow():
  for browser in TEXT_WEB_BROWSERS:
    if browser in webbrowser._tryorder:
      webbrowser._tryorder.remove(browser)

  if webbrowser._tryorder:
    webbrowser.open('http://127.0.0.1:8080/', new=1, autoraise=1)
  else:
    print 'Could not find your browser. Please open one and visit %s' % DEFAULT_URL

 
if __name__ == '__main__':
  parser = optparse.OptionParser()
  parser.add_option('-g', '--gui', dest='gui', default=False,
                    action="store_true",
                    help='Use graphical user interface (EXPERIMENTAL)')
  parser.add_option('-r', '--runs', dest='run_count', default=2, type='int',
                    help='Number of test runs to perform on each nameserver.')
  parser.add_option('-c', '--config', dest='config', default='namebench.cfg', 
                    help='Config file to use.')
  parser.add_option('-o', '--output', dest='output_file', default=False,
                    help='Filename to write query results to (CSV format).')
  parser.add_option('-i', '--input', dest='input_file',
                    default='data/top-10000.txt',
                    help='File containing a list of domain names to query.')
  parser.add_option('-t', '--tests', dest='test_count', default=50, type='int',
                    help='Number of queries per run.')
  (opt, args) = parser.parse_args()
  
  config = ConfigParser.ConfigParser()
  config.read(opt.config)

  nsl = nslookup.NSLookup()
  if nsl.AreDNSPacketsIntercepted():
    print 'XXX[ OHNO! ]XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
    print 'XX Someone upstream of this machine is doing evil things and  XX'
    print 'XX intercepting all outgoing nameserver requests. The results XX'
    print 'XX of this program may be useless. Continuing anyway...       XX'
    print 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
    print ''
  
  # Include internal & global first
  nameservers = nsl.FindUsableNameServers(config.items('primary'),
                                         internal=True, timeout=3)  
  # And the best 5 otherwise. We should test these for sanity.
  secondary = config.items('secondary')
  secondary_ips = [ x[0] for x in secondary ]
  cache_path = "%s.%s" % (SECONDARY_NS_CACHE, hash(str(secondary_ips)))
  try:
    cache = ConfigParser.ConfigParser()
    cache.read(cache_path)
    secondary = cache.items('best')
  except (IOError, ConfigParser.NoSectionError):
    print "Secondary cache not found, trying all nameservers"
    
    
  print "- Looking for best secondary NS out of %s nameservers" % len(secondary)
  secondary_servers = nsl.FindUsableNameServers(secondary)
  best = sorted(secondary_servers, key=operator.attrgetter('check_duration'))[0:SECONDARY_COUNT]  
  nameservers.extend(best)  
  cache = ConfigParser.RawConfigParser()
  cache.add_section('best')
  for ns in best:
    cache.set('best', ns.ip, ns.name)
  cache.write(open(cache_path, 'wb'))
  
  # Check for cache-collusion
  print "* Checking for servers which share a cache."
  nameservers = nsl.CheckCacheCollusion(nameservers)
  # TODO(tstromberg): Do not filter out local servers!
  print "- Ignoring nameservers which share cache with faster nameservers."
  nameservers = [ x for x in nameservers if not x.shares_with_faster ]
  
  if opt.gui:
    WebServerThread().start()
    OpenBrowserWindow()
  else:
    bmark = benchmark.NameBench(opt.input_file, run_count=opt.run_count,
                      test_count=opt.test_count, nameservers=nameservers)
    bmark.Run()
    bmark.DisplayResults()
    if opt.output_file:
      print '* Saving detailed results to %s' % opt.output_file
      bmark.SaveResultsToCsv(opt.output_file)

    best = bmark.BestOverallNameServer()
    nearest = bmark.NearestNameServer()
    print ''
    print "Recommended Configuration (fastest + nearest):"
    print "----------------------------------------------"
    print "nameserver %s\t# %s %s" % (best.ip, best.name, best.notes)
    print "nameserver %s\t# %s %s" % (nearest.ip, nearest.name, nearest.notes)
    
    