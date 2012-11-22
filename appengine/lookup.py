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
import logging
import operator
import os

from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util

from libnamebench import charts
from libnamebench import url_map

import models

class LookupHandler(webapp.RequestHandler):
  """Handler for /id/### requests."""

  def get(self, id):
    submission = models.Submission.get_by_id(int(id))
    nsdata = self.get_cached_nsdata(submission, key="ns-%s" % id)
    ns_summary = self._CreateNameServerTable(nsdata, key="ns_sum2-%s" % id)
    if not ns_summary:
      return self.response.out.write("Bummer. ID#%s (%s) has no data." % (id, submission.timestamp))
      
    recommended = [ns_summary[0]]
    reference = None
    
    for row in ns_summary:
      if row['is_reference']:
        reference = row
    
    for record in sorted(ns_summary, key=operator.itemgetter('duration_min')):      
      if record['ip'] != recommended[0]['ip']:
        recommended.append(record)
        if len(recommended) == 3:
          break

    version, config = self._GetConfigTuples(submission)
    template_values = {
      'id': id,
      'index_data': [],     # DISABLED: self._CreateIndexData(nsdata)
      'nsdata': ns_summary,
      'submission': submission,
      'reference': reference,
      'best_nameserver': submission.best_nameserver,
      'best_improvement': submission.best_improvement,
      'config': config,
      'version': version,
      'port_behavior_data': self._CreatePortBehaviorData(ns_summary, key="behavior-%s" % id),
      'nsdata': self._CreateNameServerTable(nsdata, key="table-%s" % id),
      'mean_duration_url': self._CreateMeanDurationUrl(nsdata, key="mean-%s" % id),
      'min_duration_url': self._CreateMinimumDurationUrl(nsdata, key="min-%s" % id),
      'goog_index_data': self._CreateIndexData(nsdata, 'A/www.google.com.', key=id),
      'wiki_index_data': self._CreateIndexData(nsdata, 'A/www.wikipedia.org.', key=id),
      'distribution_url_250': self._CreateDistributionUrl(nsdata, 250, key="dist250-%s" % id),
      'recommended': recommended,
    }
    path = os.path.join(os.path.dirname(__file__), 'templates', 'lookup.html')
    self.response.out.write(template.render(path, template_values))    
  
  def get_cached_nsdata(self, submission, key=None):
    # TODO(tstromberg): Add a memcache wrapper that handles the key flag
    nsdata = memcache.get(key)
    if nsdata != None:
      return nsdata
    nsdata = models.SubmissionNameServer.all().filter("submission =", submission)
    memcache.add(key, nsdata, 86400)
    return nsdata

  def _GetConfigTuples(self, submission):
    # configuration is only one row, so the for loop is kind of silly here.
    hide_keys = ['submission']
    
    show_config = []
    version = None
    for configuration in submission.config:
      for key in sorted(models.SubmissionConfig.properties().keys()):
        if key == 'version':
          version = getattr(configuration, key)
        if key not in hide_keys:
          show_config.append((key, getattr(configuration, key)))
    return (version, show_config)

  def _GetSubmissionNameServers(self, submission):
    return models.SubmissionNameServer.all().filter("submission =", submission)

  def _CreateMeanDurationUrl(self, nsdata, key=None):
    url = memcache.get(key)
    if url != None:
      return url    
    
    runs_data = [(x.nameserver.name, x.averages) for x in nsdata if not x.is_disabled]
    url = charts.PerRunDurationBarGraph(runs_data)
    memcache.add(key, url, 86400)    
    return url

  def _CreateMinimumDurationUrl(self, nsdata, key=None):
    url = memcache.get(key)
    if url != None:
      return url        
    
    fastest_nsdata = [x for x in sorted(nsdata, key=operator.attrgetter('duration_min')) if not x.is_disabled]
    min_data = [(x.nameserver, x.duration_min) for x in fastest_nsdata]
    url = charts.MinimumDurationBarGraph(min_data)
    memcache.add(key, url, 86400)
    return url

  def _CreateDistributionUrl(self, nsdata, scale, key=None):
    url = memcache.get(key)
    if url != None:
      return url

    runs_data = []
    for ns_sub in nsdata:
      results = []
      for run in ns_sub.results:
        results.extend(run.durations)
      runs_data.append((ns_sub.nameserver, results))
    url = charts.DistributionLineGraph(runs_data, scale=scale, sort_by=self._SortDistribution)
    memcache.add(key, url, 86400)
    return url

  def _SortDistribution(self, a, b):
    """Sort distribution graph by name (for now)."""
    return cmp(a[0].name, b[0].name)
    
  def get_index_record_by_name(self, record):
    key="get_index:%s" % record
    host_record = memcache.get(key)
    if host_record != None:
      return host_record
    host_record = models.IndexHost.get_by_key_name(record)
    memcache.set(key, host_record, 86400)
    return host_record

  def _CreatePortBehaviorData(self, nsdata, key=None):
    host_record = memcache.get(key)
    if host_record != None:
      return host_record

    data = []
    for row in nsdata:
      data.append("['%s','%s']," % (row['name'], row['port_behavior']))
    data = ''.join(data)
    memcache.set(key, data, 86400)
    return data


  def _CreateIndexData(self, nsdata, record, key=None):
    key = "%s:%s-2" % (key, record)
    host_record = memcache.get(key)
    if host_record != None:
      return host_record

    data = []
    logging.info("want record: %s" % record)
    host_record = self.get_index_record_by_name(record)
    logging.info("record=%s" % host_record)
    for ns in nsdata:
      name = ns.nameserver.name
      if not name:
        name = ns.nameserver.ip
      for result in ns.index_results.filter('index_host =', host_record):
        data.append("['%s',%0.1f,%i,'%s']," % (name, result.duration, result.ttl, result.response))
    data = ''.join(data)
    memcache.set(key, data, 86400)
    return data
  
  def _CreateNameServerTable(self, nsdata, key=None):
#    table = memcache.get(key)
    table = None
    if table != None:
      return table
    
    table = []
    for ns_sub in nsdata:
      table.append({
        'ip': ns_sub.nameserver.ip,
        'name': ns_sub.nameserver.name,
        'version': ns_sub.version,
        'node_ids': [x for x in ns_sub.node_ids if x],
        'is_disabled': ns_sub.is_disabled,
        'is_reference': ns_sub.is_reference,
        'sys_position': ns_sub.sys_position,
        'hostname': ns_sub.nameserver.hostname,
        'diff': ns_sub.diff,
        'check_average': ns_sub.check_average,
        'overall_average': ns_sub.overall_average,
        'duration_min': ns_sub.duration_min,
        'duration_max': ns_sub.duration_max,
        'error_count': ns_sub.error_count,
        'port_behavior': ns_sub.port_behavior,
        'timeout_count': ns_sub.timeout_count,
        'nx_count': ns_sub.nx_count,
        'notes': url_map.CreateNoteUrlTuples(ns_sub.notes)
      })
    memcache.add(key, table, 14400)
    return table
    