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
#
import cgi
import datetime
import os
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util
from django.utils import simplejson

import models
from third_party import pygeoip

MIN_QUERY_COUNT = 50
GEO_DATA_PATH = "./third_party/maxmind/GeoLiteCity.dat"
# The minimum amount of time between submissions that we list
MIN_LISTING_DELTA = datetime.timedelta(hours=8)


def _get_geoip_data(ip):
  geo = pygeoip.GeoIP(GEO_DATA_PATH, flags=pygeoip.MEMORY_CACHE)
  return geo.record_by_addr(ip)  

class ClearDuplicateIdHandler(webapp.RequestHandler):
  """Provide an easy way to clear the duplicate check id from the submissions table.
  
  Designed to be run as a cronjob.
  """

  def get(self):
    check_ts = datetime.datetime.now() - MIN_LISTING_DELTA
    cleared = 0
    for record in db.GqlQuery("SELECT * FROM Submission WHERE timestamp < :1 AND dupe_check_id = NULL", check_ts):
      record.dupe_check_id = None
      cleared += 1
      record.put()
    self.response.out.write("%s submissions older than %s cleared." % (cleared, check_ts))

class MainHandler(webapp.RequestHandler):
  """Handler for / requests"""
  def get(self):
    query = models.Submission.all()
    query.filter('listed =', True)
    query.order('-timestamp')
    recent_submissions = query.fetch(10)
    template_values = {
      'recent_submissions': recent_submissions
    }  
    path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    self.response.out.write(template.render(path, template_values))
    
class LookupHandler(webapp.RequestHandler):
  """Handler for /id/### requests."""

  def get(self, id):
    submission = models.Submission.get_by_id(int(id))
#    nameservers = mode
    
    template_values = {
      'submission': submission
    }  
    path = os.path.join(os.path.dirname(__file__), 'templates', 'lookup.html')
    self.response.out.write(template.render(path, template_values))    
    
class IndexHostsHandler(webapp.RequestHandler):
    
  """Handler for /index_requests."""
  def get(self):
    hosts = []
    for record in db.GqlQuery("SELECT * FROM IndexHost WHERE listed=True"):
      hosts.append((str(record.record_type), str(record.record_name)))
    self.response.out.write(simplejson.dumps(hosts))

class SubmitHandler(webapp.RequestHandler):
  
  """Handler for result submissions."""
  
  def _duplicate_run_count(self, class_c, dupe_check_id):
    """Check if the user has submitted anything in the last 24 hours."""
    check_ts = datetime.datetime.now() - MIN_LISTING_DELTA
    query = 'SELECT * FROM Submission WHERE class_c=:1 AND dupe_check_id=:2 AND timestamp > :3'
    duplicate_count = 0
    for record in db.GqlQuery(query, class_c, dupe_check_id, check_ts):
      duplicate_count += 1
    return duplicate_count

  def _process_index_submission(self, index_results, ns_sub, index_hosts):
    """Process the index submission for a particular host."""
    
    for host, req_type, duration, answer_count, ttl in index_results:
      results = None

      for record in index_hosts:
        if host == record.record_name and req_type == record.record_type:
          self.response.out.write("Adding %s: %s\n" % (host, record))
          results = models.IndexResult()
          results.submission_nameserver = ns_sub
          results.index_host = record
          results.duration = duration
          results.answer_count = answer_count
          results.ttl = ttl
          results.put()
          break

      if not results:
        print "Odd, %s did not match." % host

  def _find_ns_by_ip(self, ip):
    """Get an NS key for a particular IP, adding it if necessary."""
    rows = db.GqlQuery('SELECT * FROM NameServer WHERE ip = :1', ip)
    for row in rows:
      return row
    
    # If it falls back.
    ns = models.NameServer()
    ns.ip = ip
# TODO(tstromberg): Fix this to avoid UnicodeDecodeErrors
#    ns.ip_bytes = u''.join([ chr(int(x)) for x in ip.split('.') ])
    ns.listed = False
    self.response.out.write("Added ns ip=%s bytes=%s" % (ns.ip, ns.ip_bytes))
    ns.put()
    return ns
  
  def post(self):
    """Store the results from a submission. Rather long."""
    dupe_check_id = self.request.get('duplicate_check')
    data = simplejson.loads(self.request.get('data'))
    class_c_tuple = self.request.remote_addr.split('.')[0:3]
    class_c = '.'.join(class_c_tuple)
    if self._duplicate_run_count(class_c, dupe_check_id):
      listed = False
    else:
      listed = True
      
    if data['config']['query_count'] < MIN_QUERY_COUNT:
      self.response.out.write("Not listing: %s < %s" % (data['config']['query_count'], MIN_QUERY_COUNT))
      listed = False

    cached_index_hosts = []
    for record in db.GqlQuery("SELECT * FROM IndexHost WHERE listed=True"):
      cached_index_hosts.append(record)
    
    submission = models.Submission()
    submission.dupe_check_id = int(dupe_check_id)
    submission.class_c = class_c
    submission.class_c_bytes = ''.join([ chr(int(x)) for x in class_c_tuple ])
    submission.listed = listed
    submission.query_count = data['config']['query_count']
    submission.run_count = data['config']['run_count']
    submission.os_system = data['config']['platform'][0]
    submission.os_release = data['config']['platform'][1]
    submission.python_version = '.'.join(map(str, data['config']['python']))
    key = submission.put()
    self.response.out.write("Saved %s for network %s (%s). Listing: %s" % (key, class_c, dupe_check_id, listed))
    
    for nsdata in data['nameservers']:

      self.response.out.write(nsdata)
      ns_record = self._find_ns_by_ip(nsdata['ip'])
      self.response.out.write("ns %s is %s" % (ns_record, nsdata['ip']))
      ns_sub = models.SubmissionNameServer()
      ns_sub.submission = submission
      ns_sub.nameserver = ns_record
      ns_sub.averages = nsdata['averages']
      ns_sub.duration_min = nsdata['min']
      ns_sub.duration_max = nsdata['max']
      ns_sub.failed_count = nsdata['failed']
      ns_sub.nx_count = nsdata['nx']
      ns_sub.position = nsdata['position']
      ns_sub.notes = nsdata['notes']
      ns_sub_instance = ns_sub.put()
      
      for idx, run in enumerate(nsdata['durations']):
        run_results = models.RunResult()
        run_results.submission_nameserver = ns_sub
        run_results.run_number = idx
        run_results.durations = list(run)
        self.response.out.write("Wrote idx=%s results=%s" % (idx, run))
        run_results.put()

      self._process_index_submission(nsdata['index'], ns_sub_instance, cached_index_hosts)



class GeoLookupHandler(webapp.RequestHandler):

  """Handler to return location information for a given IP."""
  
  def post(self):
    """Given an IP, dump all location data."""
    ip = self.request.get('ip', os.environ.get('REMOTE_ADDR'))
    self.response.out.write(simplejson.dumps(_get_geoip_data(ip)))

  # TODO(tstromberg): Find a better way.
  get = post

def main():
  url_mapping = [
      ('/', MainHandler),
      ('/id/(\d+)', LookupHandler),
      ('/geo_lookup', GeoLookupHandler),
      ('/index_hosts', IndexHostsHandler),
      ('/tasks/clear_dupes', ClearDuplicateIdHandler),
      ('/submit', SubmitHandler)
  ]
  application = webapp.WSGIApplication(url_mapping,
                                       debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
