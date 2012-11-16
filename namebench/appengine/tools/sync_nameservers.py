#!/usr/bin/python
#!/usr/bin/env python
#
# Copyright 2010 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""A simple tool to sync nsdata from namebench.cfg into App Eninge."""

import code
import getpass
import pygeoip
import sys

base_path = "/usr/local/google_appengine"
sys.path.append(base_path)
sys.path.append('..')
sys.path.append('/Users/tstromberg/namebench')
sys.path.append('/Users/tstromberg/namebench-appengine')
from libnamebench import nameserver
from libnamebench import config
from libnamebench import addr_util

sys.path.append(base_path + "/lib/yaml/lib")
sys.path.append(base_path + "/lib/webob")
sys.path.append(base_path + "/lib/django")

from google.appengine.ext.remote_api import remote_api_stub
from google.appengine.ext import db
import models

def auth_func():
    return raw_input('Username:'), getpass.getpass('Password:')

if len(sys.argv) < 2:
    print "Usage: %s app_id [host]" % (sys.argv[0],)
app_id = sys.argv[1]
if len(sys.argv) > 2:
    host = sys.argv[2]
else:
    host = '%s.appspot.com' % app_id


(options, supplied_ns, global_ns, regional_ns) = config.GetConfiguration()
servers = []
for ip, name in global_ns:
  servers.append((ip.replace('_', ':'), name, True))
for ip, name in regional_ns:
  servers.append((ip.replace('_', ':'), name, False))

remote_api_stub.ConfigureRemoteDatastore(app_id, '/remote_api', auth_func, host)
geo_city = pygeoip.GeoIP('/usr/local/share/GeoLiteCity.dat')

print "Gathering listed IPs"
listed_ips = []
entities = models.NameServer.all().fetch(100)
while entities:
  for entity in entities:
    if entity.listed and entity.ip:
      listed_ips.append(entity.ip)
  entities = models.NameServer.all().filter('__key__ >', entities[-1].key()).fetch(250)

print "%s previously listed ips found" % len(listed_ips)
batch = []
for ip, name, is_global in servers:
  # If you would like to update all records, comment this out.
  if ip in listed_ips:
    continue
  ns = nameserver.NameServer(ip, name)
  remote_ns = models.NameServer.get_or_insert(ip)
  remote_ns.ip = ip
  remote_ns.name = name.decode('latin-1')
  if addr_util.IsPrivateIP(ip):
    remote_ns.hostname = 'internal.ip'
  else:
    remote_ns.hostname = ns.hostname
  print "%-4s - %s: %s / %s (%s)" % (len(batch), ip, name, ns.hostname, is_global)
  remote_ns.is_global = is_global
  remote_ns.is_custom = False
  remote_ns.listed = True
  if not is_global:
    remote_ns.is_regional = True
  
  if not is_global and ':' not in ip:
    details = geo_city.record_by_addr(ns.ip)
  else:
    details = {}
  
  # For a local IP, for instance.
  if details:
    city = details.get('city', None)
    if city:
      remote_ns.city = city.decode('latin-1')

    country = details.get('country_name', None)
    if country:
      remote_ns.country = country.decode('latin-1')

    remote_ns.country_code = details.get('country_code', None)

    region = details.get('region_name', None)
    if region:
      remote_ns.region = region.decode('latin-1')
    else:
      remote_ns.region = None

    if 'latitude' in details:
      remote_ns.coordinates = ','.join((str(details['latitude']), str(details['longitude'])))

    print "\t%s, %s in %s (%s)" % (remote_ns.city, remote_ns.region, remote_ns.country, remote_ns.country_code)
    print "\t%s" % details

  batch.append(remote_ns)
  if len(batch) == 100:
    print "*** Updating batch ***"
    db.put(batch)
    batch = []
    
print "* Final batch update"
db.put(batch)

#entities = models.NameServer.all().fetch(100)
#for entity in entities:
#  print entity.name
