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
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util

class IndexHost(db.Model):
  record_type = db.StringProperty()
  record_name = db.StringProperty()
  listed = db.BooleanProperty()

class NameServer(db.Model):
  ip = db.StringProperty()
  ip_bytes = db.StringProperty(multiline=True)
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
  class_c_bytes = db.StringProperty(multiline=True)
  timestamp = db.DateTimeProperty(auto_now_add=True)
  listed = db.BooleanProperty()
  query_count = db.IntegerProperty()
  run_count = db.IntegerProperty()
  os_system = db.StringProperty()
  os_release = db.StringProperty()
  python_version = db.StringProperty()
  city = db.StringProperty()
  region = db.StringProperty()
  country = db.StringProperty()
  coordinates = db.GeoPtProperty()
  
  best_nameserver = db.ReferenceProperty(NameServer, collection_name='best_submissions')
  best_improvement = db.FloatProperty()
  primary_nameserver = db.ReferenceProperty(NameServer, collection_name="primary_submissions")

class SubmissionNameServer(db.Model):
  nameserver = db.ReferenceProperty(NameServer, collection_name='submissions')
  submission = db.ReferenceProperty(Submission, collection_name='nameservers')
  overall_average = db.FloatProperty()
  averages = db.ListProperty(float)
  duration_min = db.FloatProperty()
  duration_max = db.FloatProperty()
  failed_count = db.IntegerProperty()
  nx_count = db.IntegerProperty()
  position = db.IntegerProperty()
  sys_position = db.IntegerProperty()
  improvement = db.FloatProperty()
  notes = db.ListProperty(str)

# Store one row per run for run_results, since we do not need to do much with them.
class RunResult(db.Model):
  submission_nameserver = db.ReferenceProperty(SubmissionNameServer, collection_name='results')
  run_number = db.IntegerProperty()
  durations = db.ListProperty(float)
  answer_counts = db.ListProperty(int)

# We may want to compare index results, so we will store one row per record
class IndexResult(db.Model):
  submission_nameserver = db.ReferenceProperty(SubmissionNameServer, collection_name='index_results')
  index_host = db.ReferenceProperty(IndexHost, collection_name='results')
  duration = db.FloatProperty()
  answer_count = db.IntegerProperty()
  ttl = db.IntegerProperty()
