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

"""Generate a 'replay' data file from a tcpdump capture file.

This is useful to extract DNS traffic from a real-world environment
and benchmark it against various DNS services.
"""
import subprocess
import sys
import re

filename = sys.argv[1]
if not filename:
  print "You must provide a filename."
  sys.exit(1)

cmd = 'tcpdump -r %s -n port 53' % filename
pipe = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).stdout
parse_re = re.compile(' ([A-Z]+)\? ([\-\w\.]+)')
for line in pipe:
  if '?' not in line:
    continue
  match = parse_re.search(line)
  if match:
    print ' '.join(match.groups())
  else:
    print line