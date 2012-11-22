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

"""Tricks that depend on a certain DNS provider.

Tricks that require inheritence by nameserver.py must go here, otherwise,
see providers.py for externally available functions.
"""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'


class NameServerProvider(object):

  """Inherited by nameserver."""
  
  # myresolver.info
  def GetMyResolverIpWithDuration(self):
    return self.GetIpFromNameWithDuration('self.myresolver.info.')

  def GetMyResolverHostNameWithDuration(self):
    return self.GetNameFromNameWithDuration('self.myresolver.info.')

  # OpenDNS
  def GetOpenDnsNodeWithDuration(self):
    return self.GetTxtRecordWithDuration('which.opendns.com.')[0:2]

  def GetOpenDnsInterceptionStateWithDuration(self):
    """Check if our packets are actually getting to the correct servers."""
    (node_id, duration) = self.GetOpenDnsNodeWithDuration()
    if node_id and 'I am not an OpenDNS resolver' in node_id:
      return (True, duration)
    return (False, duration)

  # UltraDNS
  def GetUltraDnsNodeWithDuration(self):
    return self.GetNameFromNameWithDuration('whoareyou.ultradns.net.')

