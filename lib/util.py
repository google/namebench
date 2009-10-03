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

"""Little utility functions."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import math
import nameserver

OPENDNS_NS = '208.67.220.220'

def CalculateListAverage(values):
  """Computes the arithmetic mean of a list of numbers."""
  return sum(values) / float(len(values))

def DrawTextBar(value, max_value, max_width=53):
  """Return a simple ASCII bar graph, making sure it fits within max_width.

  Args:
    value: integer or float representing the value of this bar.
    max_value: integer or float representing the largest bar.
    max_width: How many characters this graph can use (int)

  Returns:
    string
  """

  hash_width = max_value / max_width
  return int(math.ceil(value/hash_width)) * '#'

def TimeDeltaToMilliseconds(td):
  """Convert timedelta object to milliseconds."""
  return (td.days*86400000) + (td.seconds*1000) + (td.microseconds/1000.0)


def SplitSequence(seq, size):
  """Recipe From http://code.activestate.com/recipes/425397/ ."""
  newseq = []
  splitsize = 1.0/size*len(seq)
  for i in range(size):
    newseq.append(seq[int(round(i*splitsize)):int(round((i+1)*splitsize))])
  return newseq


def AreDNSPacketsIntercepted():
  """Check if our packets are actually getting to the correct servers."""

  opendns = nameserver.NameServer(OPENDNS_NS)
  (response, duration) = opendns.TimedRequest('TXT', 'which.opendns.com.')[0:2]
  if response and response.answer:
    for answer in response.answer:
      if 'I am not an OpenDNS resolver' in answer.to_text():
        return (True, duration)
  else:
    print '* DNS interception test failed (no response)'

  return (False, duration)
