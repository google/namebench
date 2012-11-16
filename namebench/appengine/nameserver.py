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
import operator
import os
import logging
from django.utils import simplejson
from google.appengine.api import memcache
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp import util

# our private stash of third party code
import third_party

from libnamebench import charts
import models

MAPS_API_KEY = 'ABQIAAAAUgt_ZC0I2rXmTLwIzIUALxR_qblnQoD-DakP6eidTTtErCQTehR_m1HgdQwvNF2bjiq3H5qlCIV-jQ'


def CalculateListAverage(values):
  """Computes the arithmetic mean of a list of numbers."""
  values = [x for x in values if x != None]

  if not values:
    return 0
  return sum(values) / float(len(values))


class LookupHandler(webapp.RequestHandler):
  """Handler for /ns/### requests."""

  def get(self, ip):
    nameserver = models.NameServer.get_by_key_name(ip)
    template_values = {
      'ip': ip,
      'nameserver': nameserver
    }
    path = os.path.join(os.path.dirname(__file__), 'templates', 'nameserver.html')
    self.response.out.write(template.render(path, template_values))

class UnlistedServerHandler(webapp.RequestHandler):
  """Handler for /unlisted_servers requests."""

  def get(self):
    query = models.NameServer.all()
    query.filter('listed =', False)
    query.order('-timestamp')
    for ns in query.fetch(1000):
      if ns.ip and 'x' not in ns.ip:
        self.response.out.write('%s<br />\r\n' % (ns.ip))

class DummyNameserver(object):
  name = '(Fastest Local Nameserver)'

class CountryHandler(webapp.RequestHandler):
  """Handler for /ns/### requests."""


  def get(self, country_code):
    ns_count = {}
    avg_latencies = {}

    country = None
    total = 0
    last_timestamp = None
    submissions = self.get_cached_submissions(country_code)
    for sub in submissions:
      total += 1
      if not country:
        country = sub.country
      if not last_timestamp:
        last_timestamp = sub.timestamp
    ns_data = self.cached_nameserver_table(submissions, key=country_code)
    runs_data = []
    runs_data_global = []
    ns_popular_list = sorted(ns_data.values(), key=lambda x:(x['count']), reverse=True)
    for row in ns_popular_list:
      if 'results' in row:
        if row['ip'] != '__local__' and len(runs_data) < 10:
          runs_data.append((row['ns'], row['results']))
        if row['is_global']:
          runs_data_global.append((row['ns'], row['results']))
      if 'averages' in row:
        row['overall_average'] = CalculateListAverage(row['averages'])
      else:
        row['overall_average'] = -1
      if 'positions' in row:
        row['overall_position'] = CalculateListAverage(row['positions'])
      else:
        row['overall_position'] = -1

    ns_count = {}
    template_values = {
      'country_code': country_code,
      'count': total,
      'popular_nameservers': ns_count.items(),
      'nsdata': ns_data.values(),
      'nsdata_raw': ns_data,
      'country': country,
      'maps_api_key': MAPS_API_KEY,
      'submissions': submissions,
      'recent_submissions': submissions[0:15],
      'distribution_url': self._CreateDistributionUrl(runs_data, scale=350, key="dist-%s" % country_code),
      'distribution_url_global': self._CreateDistributionUrl(runs_data_global, scale=350, key="distglobal-%s" % country_code),
      'last_update': last_timestamp
    }
    path = os.path.join(os.path.dirname(__file__), 'templates', 'country.html')
    self.response.out.write(template.render(path, template_values))

  def _SortDistribution(self, a, b):
    """Sort distribution graph by name (for now)."""
    return cmp(a[0].name, b[0].name)

  def cached_nameserver_table(self, submissions, key=None):
    key = "nstable-%s" % key
    ns_data = memcache.get(key)
    if ns_data is not None:
      return ns_data

    ns_data = {
      '__local__': {
        'name': '(Fastest local nameserver)',
        'ip': '__local__',
        'hostname': '__fastest.local__',
        'ns': DummyNameserver(),
        'count': 0,
        'is_global': True,
        'overall_position': -1,
        'positions': [],
        'averages': [],
        'results': []
      }
    }
    for sub in submissions:
      fastest_local = None
      for ns_sub in sub.nameservers:
        ip = "%s" % ns_sub.nameserver.ip
        if ip not in ns_data:
          ns_data[ip] = {
            'name': ns_sub.nameserver.name,
            'ip': ip,
            'hostname': ns_sub.nameserver.hostname,
            'ns': ns_sub.nameserver,
            'is_global': ns_sub.nameserver.is_global,
            'overall_position': -1
        }
        if not ns_sub.nameserver.is_global and (not fastest_local or ns_sub.overall_average < fastest_local.overall_average):
          fastest_local = ns_sub

        ns_data[ip]['count'] = ns_data[ip].setdefault('count', 0) + 1
        if ns_sub.position < 15:
          ns_data[ip].setdefault('positions', []).append(ns_sub.position)
        ns_data[ip].setdefault('averages', []).append(ns_sub.overall_average)

        for run in ns_sub.results:
          ns_data[ip].setdefault('results', []).extend(run.durations)

      if fastest_local:
        ns_sub = fastest_local
        ns_data['__local__']['count'] += 1
        ns_data['__local__'].setdefault('positions', []).append(ns_sub.position)
        ns_data['__local__'].setdefault('averages', []).append(ns_sub.overall_average)
        for run in ns_sub.results:
          ns_data['__local__'].setdefault('results', []).extend(run.durations)

    if not memcache.add(key, ns_data, 7200):
      logging.error("Memcache set failed.")
    return ns_data


  def get_cached_submissions(self, country_code):
    key = "submissions-%s" % country_code
    submissions = memcache.get(key)
    if submissions is not None:
      return submissions

    query = models.Submission.all()
    query.filter("country_code =", country_code)
    query.filter('listed =', True)
    query.order('-timestamp')
    submissions = query.fetch(250)
    if not memcache.add(key, submissions, 7200):
      logging.error("Memcache set failed.")
    return submissions

  def _CreateDistributionUrl(self, runs_data, scale, key=None):
    url = memcache.get(key)
    if url != None:
      return url

    url = charts.DistributionLineGraph(runs_data, scale=scale, sort_by=self._SortDistribution)
    memcache.add(key, url, 86400)
    return url


