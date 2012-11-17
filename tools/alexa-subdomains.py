#!/usr/bin/env python
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

"""Subdomain data parser for Alexa.


"""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import glob
import operator
import os
import os.path
import re
import sys
import time

if __name__ == '__main__':
  sys.path.append('..')

# See if a third_party library exists -- use it if so.
try:
  import third_party
except ImportError:
  pass


import httplib2

CACHE_DIR = os.getenv('HOME') + '/.alexa_cache'
CACHE_EXPIRATION = 86400 * 90
SLEEPY_TIME = 15
MAX_ATTEMPTS = 5
MAX_DOMAINS = 2000

NAKED_DOMAINS = ['twitter.com', 'rapidshare.com', 'perezhilton.com', 'posterous.com']


def FetchUrl(url, attempts=0):
  attempts += 1
  print >> sys.stderr, "Fetching %s (attempt %s)" % (url, attempts)
  h = httplib2.Http(CACHE_DIR, timeout=10)
  resp, content = h.request(
      url, 'GET', headers={'cache_control': 'max-age=%s' % CACHE_EXPIRATION})
  return content


def FetchCachedAlexaPage(domain):
  # Alexa sets 'cache-control': 'no-store, no-cache', so we cant' rely on httplib2.
  url_path = 'www.alexa.com/siteinfo/%s' % domain
  cache_path = '%s/%s' % (CACHE_DIR, url_path.replace('/', ','))

  if not os.path.exists(cache_path):
    contents = FetchUrl("http://%s" % url_path)
    with open(cache_path, 'w') as f:
      f.write(contents)
  else:
    contents = open(cache_path).read()
  return contents


def ParseAlexaSubdomains(content):
  return re.findall('\<p class=\"tc1.*?>([\w\.-]+\.[\w]{2,})\<\/p>.*?tc1.*?(\d+\.\d+)%', content, re.M | re.S)


def GetHostsForDomain(domain):
  content = FetchCachedAlexaPage(domain)
  return ParseAlexaSubdomains(content)


if __name__ == '__main__':
  index = 0
  results = {}

  for index, domain in enumerate(open(sys.argv[1]).readlines(), start=1):
    if index == MAX_DOMAINS:
      break
    domain = domain.rstrip()
    for host, percentage in GetHostsForDomain(domain):
      if host == domain and domain not in NAKED_DOMAINS:
        host = '.'.join(('www', domain))
      if float(percentage) < 0.01:
        continue
      score = index / (float(percentage) / 100)
      if host not in results:
        results[host] = score
      print >> sys.stderr, "[%s] %s: %s (%s)" % (index, score, host, percentage)

  for host, score in sorted(results.items(), key=operator.itemgetter(1)):
    print "A %s." % host


