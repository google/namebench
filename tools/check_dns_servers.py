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


import csv
import re
import sys
import GeoIP
sys.path.append('..')
sys.path.append('/Users/tstromberg/namebench')
import third_party
from libnamebench import nameserver_list
from libnamebench import config
from libnamebench import addr_util

import check_nameserver_popularity

gi = GeoIP.open('/usr/local/share/GeoLiteCity.dat', GeoIP.GEOIP_MEMORY_CACHE)
asn_lookup = GeoIP.open('/usr/local/share/GeoIPASNum.dat', GeoIP.GEOIP_MEMORY_CACHE)

existing_nameservers = config.GetLocalNameServerList()
check_ns = []
output = csv.writer(open('output.csv', 'w'))

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
nameserver_list.MAX_INITIAL_HEALTH_THREAD_COUNT = 100
nameservers = nameserver_list.NameServers([],
    global_servers=check_ns,
    timeout=10,
    health_timeout=10,
    threads=100,
    num_servers=5000,
    skip_cache_collusion_checks=True,
)
nameservers.min_healthy_percent = 0
sanity_checks = config.GetLocalSanityChecks()
try:
  nameservers.CheckHealth(sanity_checks['primary'], sanity_checks['secondary'])
except nameserver_list.TooFewNameservers:
  pass
print '-' * 80

for ns in nameservers:
  try:
    details = gi.record_by_addr(ns.ip)
  except:
    pass

  if not details:
    details = {}

  city = details.get('city', '')
  if city:
    city = city.decode('latin-1')
  latitude = details.get('latitude', '')
  longitude = details.get('longitude', '')
  country = details.get('country_name', '')
  if country:
    country = country.decode('latin-1')
  country_code = details.get('country_code', '')
  region = details.get('region_name', '')
  if region:
    region = region.decode('latin-1')
  
  try:
    results = check_nameserver_popularity.CheckPopularity(ns.ip)
    urls = [ x['Url'] for x in results ]
  except:
    urls = ['(exception)']
  num_urls = len(urls)
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

  if ns.hostname != ns.ip:
    domain = addr_util.GetDomainPartOfHostname(ns.hostname)
    if domain:
      good_urls = [x for x in urls if re.search(domain, x, re.I)]
      if good_urls:
        urls = good_urls

  geo = '/'.join([x for x in [country_code, region, city] if x and not x.isdigit()]).encode('utf-8')
  coords = ','.join(map(str, [latitude,longitude]))
  asn = asn_lookup.org_by_addr(ns.ip)
  row = [ns.ip, 'regional', 'UNKNOWN', '', ns.hostname, geo, coords, asn, note, num_urls, ' '.join(urls[:2]), ns.version]
  print row
  output.writerow(row)
