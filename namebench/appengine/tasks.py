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

# The minimum amount of time between submissions that we list.
# TODO(tstromberg): Fix duplication in submit.py
MIN_LISTING_DELTA = datetime.timedelta(hours=6)


class ClearDuplicateIdHandler(webapp.RequestHandler):
  """Provide an easy way to clear the duplicate check id from the submissions table.

  Designed to be run as a cronjob.
  """

  def get(self):
    check_ts = datetime.datetime.now() - MIN_LISTING_DELTA
    cleared = []
    for record in models.Submission.all().filter('client_id != ', None): 
      if record.timestamp < check_ts:
        record.client_id = None
        record.submit_id = None
        cleared.append(record)
    db.put(cleared)
    self.response.out.write("%s submissions older than %s cleared." % (len(cleared), check_ts))


class ImportIndexHostsHandler(webapp.RequestHandler):
  """Import a default list of index hosts."""

  def get(self):
    hosts = [
      ('A', 'a.root-servers.net.'), ('A', 'www.amazon.com.'),
      ('A', 'www.baidu.com.'), ('A', 'www.facebook.com.'),
      ('A', 'www.google-analytics.com.'), ('A', 'www.google.com.'),
      ('A', 'www.twitter.com.'), ('A', 'www.wikipedia.org.'),
      ('A', 'www.youtube.com.'), ('A', 'yahoo.com.'),
    ]

    for h_type, h_name in hosts:
      key = '/'.join([h_type, h_name])
      entry = models.IndexHost.get_or_insert(key, record_type=h_type, record_name=h_name, listed=True)
      self.response.out.write(entry.record_name)
