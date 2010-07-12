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

"""Add link count and version to csv"""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import csv
import check_nameserver_popularity
import sys
reader = csv.reader(open(sys.argv[1]))
writer = csv.writer(open('output.csv', 'w'))

sys.path.append('..')
#sys.path.append('/Users/tstromberg/namebench')
import third_party
from libnamebench import addr_util
from libnamebench import nameserver

for row in reader:
  ip = row[0]
  ns = nameserver.NameServer(ip)
  ns.timeout = 0.5
  ns.health_timeout = 0.5
  try:
    link_count = len(check_nameserver_popularity.GetUrls(ip))
  except:
    link_count = ''
  row.insert(-1, link_count)
  row.append(ns.version or '')
  print "%s: %s" % (ip, ns.version)
  writer.writerow(row)

