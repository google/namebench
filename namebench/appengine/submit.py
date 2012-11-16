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
import re
from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util
from django.utils import simplejson

import models

MIN_QUERY_COUNT = 100
MIN_SERVER_COUNT = 7
# The minimum amount of time between submissions that we list
# TODO(tstromberg): Fix duplication in tasks.py
MIN_LISTING_DELTA = datetime.timedelta(hours=6)

# TODO(tstromberg): Remove duplicate code - comes from libnamebench/util.py
def is_private_ip(ip):
  """Boolean check to see if an IP is private or not.
  
  Returns: Number of bits that should be preserved.
  """
  if re.match('^10\.', ip):
    return 1
  elif re.match('^192\.168', ip):
    return 2
  elif re.match('^172\.(1[6-9]|2[0-9]|3[0-1])\.', ip):
    return 1
  else:
    return None

def list_average(values):
  """Computes the arithmetic mean of a list of numbers."""
  if not values:
    return 0
  return sum(values) / float(len(values))


class SubmitHandler(webapp.RequestHandler):

  """Handler for result submissions."""

  def _duplicate_run_count(self, class_c, client_id, submit_id):
    """Check if the user has submitted anything in the last 24 hours."""
    dupes = models.Submission.all().filter("submit_id = ", submit_id).filter("class_c = ", class_c).count()
    if dupes:
      return -1
    
    check_ts = datetime.datetime.now() - MIN_LISTING_DELTA
    excess_listings = models.Submission.all().filter("client_id =", client_id).filter("class_c =", class_c).filter("timestamp > ", check_ts).filter("listed = ", True).count()
    return excess_listings

  def _process_index_submission(self, index_results, submission, ns_sub, index_hosts):
    """Process the index submission for a particular host."""

    result_list = []
    for host, req_type, duration, answer_count, ttl, response in index_results:
      results = None

      for record in index_hosts:
        if host == record.record_name and req_type == record.record_type:
          results = models.IndexResult(parent=submission)
          results.submission_nameserver = ns_sub
          results.index_host = record
          results.duration = duration
          results.answer_count = answer_count
          results.ttl = ttl
          results.response = response
          result_list.append(results)
          break

      if not results:
        print "Odd, %s did not match." % host
    
    db.put(result_list)

  def post(self):
    """Store the results from a submission. Rather long."""
    notes = []
    client_id = int(self.request.get('client_id'))
    submit_id = int(self.request.get('submit_id'))
    data = simplejson.loads(self.request.get('data'))
    ip = self.request.remote_addr
    class_c = '.'.join(ip.split('.')[0:3])
    cached_index_hosts = self.get_cached_index_hosts()
    ns_map = self.insert_nameservers_from_data(data)
    excess_listings = self._duplicate_run_count(class_c, client_id, submit_id)
    # A special handler for the unlikely case of a duplicate submit_id. 
    if excess_listings == -1:
      response = {'state': 'dupe', 'url': '/', 'notes': ["Duplicate submit_id. How'd that happen?"]}
      return self.response.out.write(simplejson.dumps(response))
    
    return db.run_in_transaction(self.insert_data, class_c, submit_id, client_id, data, ns_map,
                                 cached_index_hosts, excess_listings=excess_listings)

  def get_cached_index_hosts(self):
    index_hosts = memcache.get('index_hosts')
    if index_hosts is not None:
      return index_hosts
    
    index_hosts = []
    for record in db.GqlQuery("SELECT * FROM IndexHost WHERE listed=True"):
      index_hosts.append(record)
    if not memcache.add("index_hosts", index_hosts, 14400):
      logging.error("Memcache set failed.")
    return index_hosts

  def insert_nameservers_from_data(self, data):
    """Insert nameservers from data. Designed to run in another transaction.
    
    Caches the result for re-use by insert_data
    """

    ns_map = {}
    for nsdata in data['nameservers']:
      ns_record = models.NameServer.get_or_insert(
          nsdata['ip'],
          ip=nsdata['ip'],
          name=nsdata['name'],
          hostname=nsdata['hostname'],
          is_global=nsdata.get('is_global', False),
          is_regional=nsdata.get('is_regional', False),
          is_custom=nsdata.get('is_custom', False),
          listed=False
      )
      ns_map[nsdata['ip']] = ns_record
    return ns_map
      
  def insert_data(self, class_c, submit_id, client_id, data, ns_map, cached_index_hosts, excess_listings=None):
    """Process data uploaded by namebench."""
    
    notes = []
    listed = True
  
    if data['config']['query_count'] < MIN_QUERY_COUNT:
      notes.append("Not enough queries to list (need %s)." % MIN_QUERY_COUNT)
      listed = False

    if len(data['nameservers']) < MIN_SERVER_COUNT:
      notes.append("Not enough servers to list (need %s)." % MIN_SERVER_COUNT)
      listed = False

    if excess_listings:
      notes.append("You have already submitted a listed entry within %s" % MIN_LISTING_DELTA)
      listed = False

    submission = models.Submission()
    submission.client_id = client_id
    submission.submit_id = submit_id
    submission.class_c = class_c
    # Hide from the main index. 
    hide_me = self.request.get('hidden', False)
    # simplejson does not seem to convert booleans
    if hide_me and hide_me != 'False':
      notes.append("Hidden on request: %s [%s]" % (hide_me, type(hide_me)))
      submission.hidden = True
      listed = False
    elif is_private_ip(class_c):
      notes.append("Hidden due to internal IP.")
      submission.hidden = True
      listed = False
    else:
      submission.hidden = False
    submission.listed = listed

    if 'geodata' in data and data['geodata']:
      if 'latitude' in data['geodata']:
        submission.coordinates = ','.join((str(data['geodata']['latitude']), str(data['geodata']['longitude'])))
        submission.city = data['geodata'].get('city', None)
        submission.region = data['geodata'].get('region_name', None)
        submission.country = data['geodata'].get('country_name', None)    
        submission.country_code = data['geodata'].get('country_code', None)    
    submission.put()
    
    # Dump configuration for later reference.
    config = models.SubmissionConfig(parent=submission)
    config.submission = submission
    save_variables = [
      'query_count',
      'platform',
      'run_count',
      'benchmark_thread_count',
      'health_thread_count',
      'health_timeout',
      'timeout',
      'version',
      'input_source'
    ]
    for var in save_variables:
      if data['config'].get(var) != None:
        setattr(config, var, data['config'][var])

    config.put()
    
    for nsdata in data['nameservers']:
      # TODO(tstromberg): Look into caching this from our previous results.
      ns_record = ns_map[nsdata['ip']]
      ns_sub = models.SubmissionNameServer(parent=submission)
      ns_sub.submission = submission
      ns_sub.nameserver = ns_record
      
      save_variables = [
        'averages',
        'check_average',
        'node_ids',
        'version',
        'error_count',
        'is_disabled',
        'is_error_prone',
        'is_reference',
        'duration_max',
        'duration_min',
        'nx_count',
        'overall_average',
        'position',
        'sys_position',
        'diff',
        'port_behavior',
        'timeout_count'
      ]
      for var in save_variables:
        if nsdata.get(var) != None:
          if '_average' in var:
            setattr(ns_sub, var, float(nsdata[var]))
          else:
            setattr(ns_sub, var, nsdata[var])
        
      if nsdata['sys_position'] == 0:
        submission.primary_nameserver = ns_record
      if nsdata.get('notes'):
        # Only include the text information, not the URL.
        ns_sub.notes = [x['text'] for x in nsdata['notes']]
      ns_sub_instance = ns_sub.put()

      # The fastest ns wins a special award.
      if ns_sub.position == 0:
        submission.best_nameserver = ns_record
        if not ns_sub.sys_position == 0 and ns_sub.diff:
          submission.best_improvement = ns_sub.diff

      if nsdata.get('durations'):
        result_list = []
        for idx, run in enumerate(nsdata['durations']):
          run_results = models.RunResult(parent=submission)
          run_results.submission_nameserver = ns_sub
          run_results.run_number = idx
          run_results.durations = list(run)
          result_list.append(run_results)
        db.put(result_list)

      if nsdata.get('index'):
        self._process_index_submission(nsdata['index'], submission, ns_sub_instance,
                                       cached_index_hosts)

    # Final update with the primary_nameserver / best_nameserver data.
    submission.put()
    if listed:
      state = 'public'
      # invalidate the data for the frontpage
      memcache.delete('submissions')
    elif submission.hidden:
      state = 'hidden'
    else:
      state = 'unlisted'
    response = {
        'state': state,
        'url': '/id/%s' % submission.key().id(),
        'notes': notes
    }
    self.response.out.write(simplejson.dumps(response))
