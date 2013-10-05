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

import re
import sys
import pygeoip
sys.path.append('..')
sys.path.append('/Users/tstromberg/namebench')
import third_party
from libnamebench import nameserver_list
from libnamebench import config
from libnamebench import addr_util

geo_city = pygeoip.GeoIP('/usr/local/share/GeoLiteCity.dat')
(options, supplied_ns, global_ns, regional_ns) = config.GetConfiguration()
cfg_nameservers = global_ns + regional_ns
#cfg_nameservers = [('205.151.67.2', '205.151.67.2')]
nameservers = nameserver_list.NameServers(
    cfg_nameservers,
    timeout=30,
    health_timeout=30,
    threads=40,
    skip_cache_collusion_checks=True,
)

nameservers.PingNameServers()

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
  matches = re.search('[- ](\d+)', ns.name)
  if matches:
    instance = matches.group(1)
    ns.name = re.sub('[- ]%s' % instance, '', ns.name)
    main = u"%s=%s (%s)" % (ns.ip, ns.name, instance)
  else:
    main = u"%s=%s" % (ns.ip, ns.name)
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

  geo = '/'.join([x for x in [city, region, country] if x and not x.isdigit()])
  entry = "%-50.50s # %s, %s, %s (%s) %s" % (main, ns.hostname, latitude, longitude, geo, note)
  print entry.encode('utf-8')
