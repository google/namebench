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

"""Split instance from provider"""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import csv
import re
reader = csv.reader(open('../config/servers.csv'))
writer = csv.writer(open('output.csv', 'w'))
for row in reader:
  name = row[2]
  matches = re.match('(.*?) \((.*)\)', name)
  if matches:
    name = matches.group(1)
    instance = matches.group(2)
  else:
    instance = ''

  row[2] = name
  row.insert(3, instance)
  writer.writerow(row)

