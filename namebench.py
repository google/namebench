#!/usr/bin/env python
# Copyright 2009 Google Inc. All Rights Reserved.

"""Simple DNS server comparison benchmarking tool.

Designed to assist system administrators in selection and prioritization.
"""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import ConfigParser
import optparse
import sys
import tempfile

# Make it easy to import 3rd party utilities without editing their imports.
sys.path.append('lib/third_party')

from lib import benchmark
from lib import nslookup
from lib import web

VERSION = '0.5'


def RetrieveSecondaryDNSCache(path):
  """Try to get the best secondary servers out of the cache."""
  try:
    cache = ConfigParser.ConfigParser()
    cache.read(path)
    print "- Read cached secondary servers from %s" % path
    return cache.items('best')
  except (IOError, ConfigParser.NoSectionError):
    return None


def UpdateSecondaryDNSCache(path, best_secondary):
  """Update the secondary DNS cache file."""
  cache = ConfigParser.RawConfigParser()
  cache.add_section('best')
  for ns in best_secondary:
    cache.set('best', ns.ip, ns.name)
  cache.write(open(path, 'wb'))


def ExcludeSharedCacheServers(try_nameservers):
  """Filter out servers if they are simply slower replicas."""
  nst = nslookup.NameServerTests()
  checked = nst.CheckCacheCollusion(try_nameservers)
  return [x for x in checked if x.is_healthy and not x.shares_with_faster]


def PickAwesomeNameServers(primary, secondary, timeout, max_threads,
                           secondary_count):
  """Return a list of good working nameservers to test against.

  Args:
    primary: A list of (ip, name) tuples
    secondary: A list of (ip, name) tuples
    timeout: # of seconds to timeout.
    max_threads: # of threads to use (int)
    secondary_count: # of secondary servers to select from.

  Returns:
    A list of NameServerData objects with healthy servers.
  """
  print '- Checking the health of %s primary servers' % (len(primary))
  nst = nslookup.NameServerTests(thread_count=max_threads, timeout=timeout)
  try_nameservers = nst.FindUsableNameServers(primary, internal=True)
  secondary_hash = hash(str([x[0] for x in secondary]))
  cache_path = '%s/namebench_cache.%s' % (tempfile.gettempdir(),
                                          secondary_hash)
  cached_secondary = RetrieveSecondaryDNSCache(cache_path)
  if cached_secondary:
    secondary = cached_secondary

  print '- Checking the health of %s secondary servers' % (len(secondary))
  secondary_servers = nst.FindUsableNameServers(secondary)
  best_secondary = secondary_servers[0:secondary_count]
  if not cached_secondary:
    UpdateSecondaryDNSCache(cache_path, best_secondary)

  try_nameservers.extend(best_secondary)
  print "- Excluding slowest nameservers that share a cache..."
  return ExcludeSharedCacheServers(try_nameservers)


if __name__ == '__main__':

  parser = optparse.OptionParser()
  parser.add_option('-g', '--gui', dest='gui', default=False,
                    action='store_true',
                    help='Use graphical user interface (EXPERIMENTAL)')
  parser.add_option('-r', '--runs', dest='run_count', default=2, type='int',
                    help='Number of test runs to perform on each nameserver.')
  parser.add_option('-c', '--config', dest='config', default='namebench.cfg',
                    help='Config file to use.')
  parser.add_option('-o', '--output', dest='output_file', default=False,
                    help='Filename to write query results to (CSV format).')
  parser.add_option('-T', '--threads', dest='thread_count', default=False,
                    help='# of threads to use')
  parser.add_option('-i', '--input', dest='input_file',
                    default='data/top-10000.txt',
                    help='File containing a list of domain names to query.')
  parser.add_option('-t', '--tests', dest='test_count', default=50, type='int',
                    help='Number of queries per run.')
  (opt, args) = parser.parse_args()

  config = ConfigParser.ConfigParser()
  config.read(opt.config)
  general = dict(config.items('general'))
  primary_ns = config.items('primary')
  secondary_ns = config.items('secondary')

  # Include internal & global first
  if opt.thread_count:
    thread_count = int(opt.thread_count)
  else:
    thread_count = int(general['max_thread_count'])

  print ('namebench %s - %s threads, %s tests, %s runs' %
         (VERSION, thread_count, opt.test_count, opt.run_count))
  print '-' * 78

  for arg in args:
    if '.' in arg:
      print '- Adding %s from command-line' % arg
      primary_ns.append((arg, arg))

  test = nslookup.NameServerTests()
  if test.AreDNSPacketsIntercepted():
    print 'XXX[ OHNO! ]XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
    print 'XX Someone upstream of this machine is doing evil things and  XX'
    print 'XX intercepting all outgoing nameserver requests. The results XX'
    print 'XX of this program may be useless. Continuing anyway...       XX'
    print 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
    print ''

  nameservers = PickAwesomeNameServers(primary_ns, secondary_ns,
                                       int(general['health_timeout']),
                                       thread_count,
                                       int(general['secondary_count']))
  if opt.gui:
    web.WebServerThread().start()
    web.OpenBrowserWindow()
  else:
    bmark = benchmark.NameBench(opt.input_file, run_count=opt.run_count,
                                test_count=opt.test_count,
                                nameservers=nameservers)
    bmark.Run()
    bmark.DisplayResults()
    if opt.output_file:
      print '* Saving detailed results to %s' % opt.output_file
      bmark.SaveResultsToCsv(opt.output_file)

    best = bmark.BestOverallNameServer()
    nearest = bmark.NearestNameServer()
    print ''
    print 'Recommended Configuration (fastest + nearest):'
    print '----------------------------------------------'
    print 'nameserver %s \t# %s %s' % (best.ip, best.name,
                                      ', '.join(best.notes))
    print 'nameserver %s \t# %s %s' % (nearest.ip, nearest.name,
                                      ', '.join(nearest.notes))

