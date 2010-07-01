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

"""Tool to convert listing to CSV format."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import csv
import re
import sys
import check_nameserver_popularity
import GeoIP
sys.path.append('..')
#sys.path.append('/Users/tstromberg/namebench')
import third_party
from libnamebench import nameserver_list
from libnamebench import config

output = csv.writer(open('servers.csv', 'w'))
#output.writerow(['IP', 'Name', 'Hostname', 'Country/Region/City', 'Coords', 'ASN', 'Label', 'Status', 'Refs'])
gi = GeoIP.open('/usr/local/share/GeoLiteCity.dat', GeoIP.GEOIP_MEMORY_CACHE)
asn_lookup = GeoIP.open('/usr/local/share/GeoIPASNum.dat', GeoIP.GEOIP_MEMORY_CACHE)
ns_hash = config.GetLocalNameServerList()
for ip in ns_hash:
  try:
    details = gi.record_by_addr(ip)
  except SystemError:
    pass

  if not details:
    details = {}
  city = details.get('city', '')
  if city:
    city = city.decode('latin-1')
  country = details.get('country_name', '')
  if country:
    country = country.decode('latin-1')
  latitude = details.get('latitude', '')
  longitude = details.get('longitude', '')
  country_code = details.get('country_code', '')
  region = details.get('region_name', '')
  if region:
    region = region.decode('latin-1')

  hostname = ns_hash[ip].get('hostname', '')
  geo = '/'.join([x for x in [country_code, region, city] if x and not x.isdigit()]).encode('utf-8')
  coords = ','.join(map(str, [latitude,longitude]))
  status = ns_hash[ip].get('notes', '')
  refs = None
  asn = asn_lookup.org_by_addr(ip)
  labels = ' '.join(list(ns_hash[ip]['labels']))
  search_results = check_nameserver_popularity.CheckPopularity(ip)
  class_b = '.'.join(ip.split('.')[0:2])
  suffix = '.'.join(ip.split('.')[-2:])
  middle = '.'.join(ip.split('.')[1:3])
  banned_urls = [ class_b, suffix, middle, '\.xls$', '\.txt$', 'spam',
                  'nettools', 'namebench', 'spam', 'affinity-v1',
                  'corporationwiki', 'iptools', 'whois', 'iana.org',
                  'public.*dns', 'blocked', 'firewall', 'websitevaluespy',
                  'iptool', 'sshd-versions', '\.off$']

  use_keywords = set()
  if ns_hash[ip]['name'] and 'UNKNOWN' not in ns_hash[ip]['name']:
    for word in ns_hash[ip]['name'].split(' ')[0].split('/'):
      use_keywords.add(word.lower())
      use_keywords.add(re.sub('[\W_]', '', word.lower()))

      if '-' in word:
        use_keywords.add(word.lower().replace('-', ''))

  if hostname and hostname != ip:
    print "host: %s ip: %s" % (hostname, ip)
    host_parts = hostname.split('.')
    if len(host_parts) > 3 and (len(host_parts[-2]) < 3 or host_parts[-2] in ('edu', 'com', 'net')):
      use_keywords.add(host_parts[-3].lower())
    else:
      use_keywords.add(host_parts[-2].lower())

  for bad_word in ('ns', 'dns'):
    if bad_word in use_keywords:
      use_keywords.remove(bad_word)
  print use_keywords
  urls = []
  best_urls = []
  for result in search_results:
    reject = False
    for keyword in banned_urls:
      if re.search(keyword, result['Url'], re.I):
        reject = True

    if not reject:
      for keyword in use_keywords:
        if re.search(keyword, result['Url'], re.I):
          best_urls.append(result['Url'])
          break
      urls.append(result['Url'])

  if best_urls:
    urls = best_urls
  row = [ip, labels, ns_hash[ip]['name'], hostname, geo, coords, asn, status[0:30], ' '.join(urls[:2])]
  print row
  output.writerow(row)
