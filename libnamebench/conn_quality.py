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
import time
sys.path.append('third_party')

import nameserver
import util

OPENDNS_NS = '208.67.220.220'
GOOGLE_NS = '8.8.8.8'
EXPECTED_CONGESTION_DURATION = 40.0
CONGESTION_OFFSET_MULTIPLIER = 1
MAX_CONGESTION_MULTIPLIER = 3

class ConnectionQuality(object):

  def __init__(self, status_callback=None):
    self.status_callback = status_callback

  def msg(self, msg, **kwargs):
    if self.status_callback:
      self.status_callback(msg, **kwargs)
    else:
      print msg

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
    """Use the built-in DNS server to query for a negative response."""
    internal = util.InternalNameServers()
    # In rare cases, we may not find any to use.
    if not internal:
      return 0

    primary_ip = internal[0]
    primary = nameserver.NameServer(primary_ip)
    return primary.TestNegativeResponse()[2]

  def GetGoogleResponseDuration(self):
    """See how quickly we can query for www.google.com using a remote nameserver."""
    gdns = nameserver.NameServer(GOOGLE_NS)
    (response, duration) = gdns.TimedRequest('A', 'www.google.com.')[0:2]
    return (duration)


  def CheckConnectionQuality(self):
    """Look how healthy our DNS connection quality. Pure guesswork."""
    self.msg('Checking connection quality...')
    durations  = []

    for i in range(2):
      (intercepted, i_duration) = self.GetInterceptionStatus()
      n_duration = self.GetNegativeResponseDuration()
      g_duration = self.GetGoogleResponseDuration()
      durations.extend([i_duration, n_duration, g_duration])
      time.sleep(0.5)

    duration = util.CalculateListAverage(durations)
    congestion = duration / EXPECTED_CONGESTION_DURATION
    self.msg('Congestion level is %2.2fX (check duration: %2.2fms)' % (congestion, duration))
    if congestion > 1:
      # multiplier is
      multiplier = 1 + ((congestion-1) * CONGESTION_OFFSET_MULTIPLIER)
      if multiplier > MAX_CONGESTION_MULTIPLIER:
        multiplier = MAX_CONGESTION_MULTIPLIER
    else:
      multiplier = 1
    return (intercepted, congestion, multiplier, duration)
