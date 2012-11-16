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

"""Get the total number of submissions per country."""

import code
import datetime
import getpass
import operator
import re
import pygeoip
import sys

base_path = "/usr/local/google_appengine"
sys.path.append(base_path)
sys.path.append('..')
sys.path.append('/Users/tstromberg/namebench-appengine')

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
host = '%s.appspot.com' % app_id

if len(sys.argv) > 2:
  days = int(sys.argv[2])
else:
  days = 7

remote_api_stub.ConfigureRemoteDatastore(app_id, '/remote_api', auth_func, host)
since = datetime.datetime.now() - datetime.timedelta(days=days)
print "Gathering totals since %s" % since
country_total = {}
best_ns_total = {}
current_ns_total = {}
source_total = {}
grand_total = 0
seen_subs = []
seen_nets = []
NS_CACHE = {}
entities = models.Submission.all().filter('listed = ', True).filter('timestamp > ', since).order('-timestamp').fetch(100)
while entities:
  print len(entities)
  for entity in entities:
    if entity.class_c in seen_nets:
      print "(ignoring submission, already seen %s)" % entity.class_c
      continue
    if entity.key() in seen_subs:
      print "duplicate key: %s" % entity.key()
      break
      
    seen_subs.append(entity.key())
    seen_nets.append(entity.class_c)
    country_total[entity.country] = country_total.setdefault(entity.country, 0) + 1
    current_ns_total[entity._primary_nameserver] = current_ns_total.setdefault(entity._primary_nameserver, 0) + 1
    best_ns_total[entity._best_nameserver] = best_ns_total.setdefault(entity._best_nameserver, 0) + 1
    grand_total += 1

  # bad assumption, may miss two submissions sent at the exact same time.    
  entities = models.Submission.all().filter('timestamp <', entity.timestamp).filter('listed =', True).filter('timestamp > ', since).order('-timestamp').fetch(100)

#entities = models.SubmissionConfig.all().fetch(100)
#while entities:
#  for entity in entities:
#    if entity._submission in seen_subs:
#      source_total[entity.input_source] = source_total.setdefault(entity.input_source, 0) + 1
#    
#  entities = models.SubmissionConfig.all().filter('__key__ >', entities[-1].key()).fetch(100)

print "COUNTRY: %s" % grand_total
print "-" * 70
for key in country_total:
  count = country_total[key]
  print "%s\t%s (%.1f%%)" % (count, key, (count / float(grand_total)) * 100)

#print "SOURCE: %s" % grand_total
#print "-" * 70
#for key in source_total:
#  count = source_total[key]
#  print "%s\t%s (%.1f%%)" % (count, key, (count / float(grand_total)) * 100)

def _GetCachedNsName(key):
  if key not in NS_CACHE:
    try:
      ns = models.NameServer.get(key)
      NS_CACHE[key] = ns.name or ns.ip
    except:
      NS_CACHE[key] = 'ERR-%s' % key
  return NS_CACHE[key]
  
def _ShowNameServersByCount(data, count=150):
  top_by_name = {}
  top_ns_items = sorted(data.items(), key=operator.itemgetter(1))
  top_ns_items.reverse()
  for key, count in top_ns_items[:count]:
    name = _GetCachedNsName(key)
    name = re.sub('-\d+$', '', name)
    name = re.sub('-\d+ ', ' ', name)
    name = re.sub(' \d+ ', ' ', name)
    if name.startswith('Internal') or name.endswith('.x'):
      name = 'Internal IP'
    top_by_name[name] = top_by_name.setdefault(name, 0) + count

  top_names = sorted(top_by_name.items(), key=operator.itemgetter(1))
  top_names.reverse()
  for name, count in top_names:
    print "%s\t%s (%.1f%%)" % (count, name, (count / float(grand_total)) * 100)

print
print "Best Top 150: %s" % grand_total
print "-" * 70
_ShowNameServersByCount(best_ns_total)

print
print "Current Top 150: %s" % grand_total
print "-" * 70
_ShowNameServersByCount(current_ns_total)
