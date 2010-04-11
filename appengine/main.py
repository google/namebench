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
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from django.utils import simplejson

MIN_QUERY_COUNT = 50

class IndexHost(db.Model):
  record_type = db.StringProperty()
  record_name = db.StringProperty()
  listed = db.BooleanProperty()

class NameServer(db.Model):
  ip = db.StringProperty()
  ip_bytes = db.StringProperty()
  name = db.StringProperty()
  listed = db.BooleanProperty()
  city = db.StringProperty()
  province = db.StringProperty()
  country = db.StringProperty()
  coordinates = db.GeoPtProperty()
  url = db.LinkProperty()
  timestamp = db.DateTimeProperty(auto_now_add=True)

class Submission(db.Model):
  dupe_check_id = db.IntegerProperty()
  class_c = db.StringProperty()
  # ByteStringProperty causes problems:
  #  File "google/appengine/ext/admin/__init__.py", line 916, in get
  #    return _DATA_TYPES[value.__class__]
  # KeyError: <class 'google.appengine.api.datastore_types.ByteString'>
  class_c_bytes = db.StringProperty()
  timestamp = db.DateTimeProperty(auto_now_add=True)
  listed = db.BooleanProperty()
  query_count = db.IntegerProperty()
  run_count = db.IntegerProperty()
  os_system = db.StringProperty()
  os_release = db.StringProperty()
  python_version = db.StringProperty()
  city = db.StringProperty()
  province = db.StringProperty()
  country = db.StringProperty()
  coordinates = db.GeoPtProperty()

class SubmissionNameServer(db.Model):
  nameserver = db.ReferenceProperty(NameServer, collection_name='submissions')
  submission = db.ReferenceProperty(Submission, collection_name='nameservers')
  averages = db.ListProperty(int)
  duration_min = db.IntegerProperty()
  duration_max = db.IntegerProperty()
  failed_count = db.IntegerProperty()
  notes = db.ListProperty(str)
  
# Store one row per run for run_results, since we do not need to do much with them.
class RunResults(db.Model):
  submission_nameserver = db.ReferenceProperty(SubmissionNameServer, collection_name='results')
  run_number = db.IntegerProperty()
  durations = db.ListProperty(int)
  answer_counts = db.ListProperty(int)

# We may want to compare index results, so we will store one row per record
class IndexResults(db.Model):
  submission_nameserver = db.ReferenceProperty(SubmissionNameServer, collection_name='index_results')
  index_host = db.ReferenceProperty(IndexHost, collection_name='results')
  duration = db.IntegerProperty()
  answer_count = db.IntegerProperty()
  
class ClearDuplicateIdHandler(webapp.RequestHandler):
  """Provide an easy way to clear the duplicate check id from the submissions table.
  
  Designed to be run as a cronjob.
  """

  def get(self):
    check_ts = datetime.datetime.now() - datetime.timedelta(days=1)
    cleared = 0
    for record in db.GqlQuery("SELECT * FROM Submission WHERE timestamp < :1 AND dupe_check_id = NULL", check_ts):
      record.dupe_check_id = None
      cleared += 1
      record.put()
    self.response.out.write("%s submissions older than %s cleared." % (cleared, check_ts))

class MainHandler(webapp.RequestHandler):

  def get(self):
    self.response.out.write('Hello world!')
    
class IndexHostsHandler(webapp.RequestHandler):
    
  def get(self):
    hosts = []
    for record in db.GqlQuery("SELECT * FROM IndexHost WHERE listed=True"):
      hosts.application((str(record.record_type), str(record.record_name)))
    self.response.out.write(hosts)

class ResultsHandler(webapp.RequestHandler):
  
  def _duplicate_run_count(self, class_c, dupe_check_id):
    """Check if the user has submitted anything in the last 24 hours."""
    check_ts = datetime.datetime.now() - datetime.timedelta(days=1)
    query = 'SELECT * FROM Submission WHERE class_c=:1 AND dupe_check_id=:2 AND timestamp > :3'
    duplicate_count = 0
    for record in db.GqlQuery(query, class_c, dupe_check_id, check_ts):
      duplicate_count += 1
    return duplicate_count
  
  def post(self):
    dupe_check_id = self.request.get('duplicate_check')
    data = simplejson.loads(self.request.get('data'))
    class_c_tuple = self.request.remote_addr.split('.')[0:3]
    class_c = '.'.join(class_c_tuple)
    if self._duplicate_run_count(class_c, dupe_check_id):
      listed = False
    else:
      listed = True
      
    if data['config']['query_count'] < MIN_QUERY_COUNT:
      listed = False
    
    submission = Submission()
    submission.dupe_check_id = int(dupe_check_id)
    submission.class_c = class_c
    submission.class_c_bytes = ''.join([ chr(int(x)) for x in class_c_tuple ])
    submission.listed = listed
    submission.query_count = data['config']['query_count']
    submission.run_count = data['config']['run_count']
    submission.os_system = data['config']['platform'][0]
    submission.os_release = data['config']['platform'][1]
    submission.python_version = '.'.join(data['config']['python'])
    key = submission.put()
    self.response.out.write("Saved %s for network %s (%s). Listing: %s" % (key, class_c, dupe_check_id, listed))

def main():
  url_mapping = [
      ('/', MainHandler),
      ('/index_hosts', IndexHostsHandler),
      ('/clear_dupes', ClearDuplicateIdHandler),
      ('/results', ResultsHandler)
  ]
  application = webapp.WSGIApplication(url_mapping,
                                       debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()
