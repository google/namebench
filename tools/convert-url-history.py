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

"""Generate a data file based on an input file containing URL's.

This outputs a "weighted" (top hits first) data file for namebench
to use. Ignores subsequent hits for the same site.
"""
import operator
import sys
import re

filename = sys.argv[1]
if not filename:
  print "You must provide a filename."
  sys.exit(1)

parse_re = re.compile('\w+://([\-\w\.]+)')
hits = {}
last_host = None

matches = parse_re.findall(open(filename).read())
for host in matches:
  if host != last_host:
    hits[host] = hits.get(host, 0) + 1
    last_host = host

top_hits = sorted(hits.items(), key=operator.itemgetter(1),reverse=True)
for (hit, count) in top_hits:
  print 'A %s\t# %s hits' % (hit, count)

