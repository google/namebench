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
MAX_CONGESTION_MULTIPLIER = 4

class OfflineConnection(Exception):

  def __init__(self, value):
    self.value = value

  def __str__(self):
    return str(self.value)

class ConnectionQuality(object):

  def __init__(self, status_callback=None):
    self.status_callback = status_callback
    self.primary = self.GetSystemPrimaryNameServer()

  def msg(self, msg, **kwargs):
    if self.status_callback:
      self.status_callback(msg, **kwargs)
    else:
      print '- %s' % msg

  def GetInterceptionStatus(self):
    """Check if our packets are actually getting to the correct servers."""

    opendns = nameserver.NameServer(OPENDNS_NS)
    (response, duration) = opendns.TimedRequest('TXT', 'which.opendns.com.')[0:2]
    if response and response.answer:
      for answer in response.answer:
        if 'I am not an OpenDNS resolver' in answer.to_text():
          return (True, duration)
    else:
      self.msg('DNS interception test failed (no response)')
      return (False, None)

    return (False, duration)
    
  def GetSystemPrimaryNameServer(self):
    """Return a nameserver object for the system primary."""
    
    internal = util.InternalNameServers()
    # In rare cases, we may not find any to use.
    if not internal:
      return None
    else:
      primary_ip = internal[0]
      return nameserver.NameServer(primary_ip)
    
  def GetNegativeResponseDuration(self):
    """Use the built-in DNS server to query for a negative response."""
    return self.primary.TestNegativeResponse()

  def GetGoogleResponseDuration(self):
    """See how quickly we can query for www.google.com using a remote nameserver."""
    gdns = nameserver.NameServer(GOOGLE_NS)
    return gdns.TimedRequest('A', 'www.google.com.')

  def CheckConnectionQuality(self):
    """Look how healthy our DNS connection quality. Averages check durations."""
    
    is_connection_offline = True
    durations  = []
    self.msg('Checking query interception status...')
    (intercepted, i_duration) = self.GetInterceptionStatus()
    if i_duration:
      is_connection_offline = False
    
    durations.append(i_duration)

    try_count = 2
    for i in range(try_count):
      self.msg('Checking connection quality', count=i+1, total=2)
      (broken, warning, n_duration) = self.GetNegativeResponseDuration()
      if not broken:
        is_connection_offline = False

      (response, g_duration, error_msg) = self.GetGoogleResponseDuration()
      durations.extend([n_duration, g_duration])
      if not error_msg:
        is_connection_offline = False

      if is_connection_offline and (i+1) != try_count:
        self.msg('The internet connection appears to be offline (%s of %s)' % (i+1, try_count))
      time.sleep(0.2)
        
    
    if is_connection_offline:
      raise OfflineConnection('It would appear that your internet connection is offline. '
                              'namebench is not gettng a response for DNS queries to '
                              '%s, %s, or %s.' % (self.primary.ip, GOOGLE_NS, OPENDNS_NS))

    if None in durations:
      self.msg('Odd, empty duration found: %s' % durations)
      durations = [ x for x in durations if x != None ]
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
