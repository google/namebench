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

"""Tool for checking a lot of DNS servers from stdin for possible inclusion."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'


import sys
import pygeoip
sys.path.append('..')
sys.path.append('/Users/tstromberg/namebench')
import third_party
from libnamebench import nameserver_list
from libnamebench import config
from libnamebench import addr_util

import check_nameserver_popularity

existing_nameservers = config.GetLocalNameServerList()
check_ns = []

for line in sys.stdin:
  ips = addr_util.ExtractIPsFromString(line)
  for ip in ips:
    print ip
    # disable IPV6 until we can improve our regular expression matching
    if ':' in ip:
      continue

    if ip not in existing_nameservers:
      check_ns.append((ip, ip))

if not check_ns:
  print "no new servers to check"
  sys.exit(1)
else:
  print "%s servers to check" % len(check_ns)
print '-' * 80

nameservers = nameserver_list.NameServers(
    check_ns,
    timeout=10,
    health_timeout=10,
    threads=100,
    skip_cache_collusion_checks=True,
)
nameservers.min_healthy_percent = 0
sanity_checks = config.GetLocalSanityChecks()
try:
  nameservers.CheckHealth(sanity_checks['primary'], sanity_checks['secondary'])
except nameserver_list.TooFewNameservers:
  pass
print '-' * 80
geo_city = pygeoip.GeoIP('/usr/local/share/GeoLiteCity.dat')

for ns in nameservers:
  if ':' in ns.ip:
    details = {}
  else:
    try:
      details = geo_city.record_by_addr(ns.ip)
    except:
      pass
    
  if not details:
    details = {}
  city = details.get('city', '').decode('latin-1')
  latitude = details.get('latitude', '')
  longitude = details.get('longitude', '')
  country = details.get('country_name', '').decode('latin-1')
  country_code = details.get('country_code', '')
  region = details.get('region_name', '').decode('latin-1')
  results = check_nameserver_popularity.CheckPopularity(ns.ip)
  urls = [ x['Url'] for x in results ]
  main = "%s=UNKNOWN" % ns.ip

  if 'Responded with: REFUSED' in ns.warnings:
    note = '_REFUSED_'
  elif 'a.root-servers.net.: Timeout' in ns.warnings:
    note = '_TIMEOUT_'
  elif 'No answer (NOERROR): a.root-servers.net.' in ns.warnings:
    note = '_NOANSWER_'
  elif ns.warnings:
    note = '_WARNING/%s_' % '/'.join(list(ns.warnings))
  else:
    note = '' 

  if urls:
    note = note + ' ' + ' '.join(urls[:2])
  geo = '/'.join([x for x in [city, region, country_code] if x and not x.isdigit()])
  entry = "%-52.52s # %s,%s,%s (%s) %s" % (main, ns.hostname, latitude, longitude, geo, note)
  print entry.encode('utf-8')
