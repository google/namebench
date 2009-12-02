#!/usr/bin/python
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
from libnamebench import util

(options, supplied_ns, global_ns, regional_ns) = config.GetConfiguration()
has_ip = [ x[0] for x in regional_ns ]
has_ip.extend([ x[0] for x in global_ns ])
check_ns = []

for line in sys.stdin:
  ips = util.ExtractIPsFromString(line)
  for ip in ips:
    if ip not in has_ip:
      check_ns.append((ip, ip))

if not check_ns:
  print "no new servers to check"
  sys.exit(1)
else:
  print "%s servers to check" % len(check_ns)
print '-' * 80
    
nameservers = nameserver_list.NameServers(
    check_ns,
    timeout=18,
    health_timeout=18,
    threads=250,
    skip_cache_collusion_checks=True,
)
nameservers.CheckHealth()
print '-' * 80
geo_city = pygeoip.GeoIP('/usr/local/share/GeoLiteCity.dat')

for ns in nameservers.enabled:
  details = geo_city.record_by_addr(ns.ip)
  city = details.get('city', '')
  country = details.get('country_name', '')
  region = details.get('region_name', '')
  print "%s=%s %s (%s, %s) %s" % (ns.ip, ns.hostname, city, region, country, ns.warnings_comment)


