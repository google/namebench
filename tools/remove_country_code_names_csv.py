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

"""Remove country codes from name column of server csv"""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import csv
reader = csv.reader(open('../config/servers.csv'))
writer = csv.writer(open('servers.csv', 'w'))
for row in reader:
  country = row[4].split('/')[0]
  row[2] = row[2].replace(' %s' % country, '')
  writer.writerow(row)

