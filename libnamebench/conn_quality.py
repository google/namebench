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

import time

import nameserver
import providers
import sys_nameservers
import util

EXPECTED_CONGESTION_DURATION = 40.0
CONGESTION_OFFSET_MULTIPLIER = 1
MAX_CONGESTION_MULTIPLIER = 6


class OfflineConnection(Exception):

  def __init__(self, value):
    self.value = value

  def __str__(self):
    return str(self.value)


class ConnectionQuality(object):

  """Methods related to connection quality detection."""

  def __init__(self, status_callback=None):
    self.status_callback = status_callback
    self.primary = providers.SystemResolver()

  def msg(self, msg, **kwargs):
    if self.status_callback:
      self.status_callback(msg, **kwargs)
    else:
      print '- %s' % msg

  def GetNegativeResponseDuration(self):
    """Use the built-in DNS server to query for a negative response."""
    if self.primary:
      self.primary.health_timeout = 20
      return self.primary.TestNegativeResponse()

  def GetGoogleResponseDuration(self):
    """See how quickly we can query for www.google.com using a remote nameserver."""
    gdns = providers.GooglePublicDNS()
    gdns.health_timeout = 20
    return gdns.TimedRequest('A', 'www.google.com.')

  def CheckConnectionQuality(self):
    """Look how healthy our DNS connection quality. Averages check durations."""

    is_connection_offline = True
    self.msg('Checking query interception status...')
    odns = providers.OpenDNS()
    (intercepted, i_duration) = odns.InterceptionStateWithDuration()
    if i_duration:
      is_connection_offline = False

    durations = []
    try_count = 3
    for i in range(try_count):
      self.msg('Checking connection quality', count=i+1, total=try_count)
      if self.primary:
        (broken, unused_warning, n_duration) = self.GetNegativeResponseDuration()
        if not broken:
          is_connection_offline = False
          durations.append(n_duration)

      (unused_response, g_duration, error_msg) = self.GetGoogleResponseDuration()

      if not error_msg:
        durations.append(g_duration)
        is_connection_offline = False

      if is_connection_offline and (i+1) != try_count:
        self.msg('The internet connection appears to be offline (%s of %s)' % (i+1, try_count))
      time.sleep(0.2)

    if is_connection_offline:
      raise OfflineConnection('It would appear that your internet connection is offline.'
                              'namebench is not gettng a response for DNS queries to '
                              '%s, %s, or %s.' % (self.primary.ip, providers.GOOGLE_IP,
                                                  providers.OPENDNS_IP))
    avg_latency_s =  util.CalculateListAverage(durations) / 1000.0
    max_latency_s = max(durations) / 1000.0
    self.msg("Average DNS lookup latency: %.2fs Maximum: %.2fs" % (avg_latency_s, max_latency_s))
    return (intercepted, avg_latency_s, max_latency_s)

