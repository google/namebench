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

"""Tests to determine connection quality."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import sys
sys.path.append('third_party')

import nameserver
import util

OPENDNS_NS = '208.67.220.220'
EXPECTED_CONGESTION_DURATION = 90.0

class ConnectionQuality(object):
  def GetInterceptionStatus(self):
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

  def GetNegativeResponseDuration(self):
    primary_ip = util.InternalNameServers()[0]
    primary = nameserver.NameServer(primary_ip)
    return primary.TestNegativeResponse()[2]

  def CheckConnectionQuality(self):
    (intercepted, i_duration) = self.GetInterceptionStatus()
    g_duration = self.GetNegativeResponseDuration()
    duration = util.CalculateListAverage((i_duration, g_duration))
    congestion = duration / EXPECTED_CONGESTION_DURATION
    print '- Intercept query took %.1fms, Congestion query took %.1fms' % (i_duration, g_duration)
    if congestion > 1:
      print '- Queries are running %.1fX slower than expected, increasing timeouts.' % congestion
    return (intercepted, congestion)
