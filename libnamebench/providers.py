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

"""Specific connections to DNS server providers."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import sys

if __name__ == '__main__':
  sys.path.append('..')
  import nb_third_party

import addr_util
import nameserver
import sys_nameservers

OPENDNS_IP = '208.67.220.220'
MY_RESOLVER_IP = '188.165.43.98'
GOOGLE_IP = '8.8.8.8'


class OpenDNS(nameserver.NameServer):
  def __init__(self, ip=OPENDNS_IP):
    super(OpenDNS, self).__init__(ip=ip)

  def InterceptionStateWithDuration(self):
    return self.GetOpenDnsInterceptionStateWithDuration()

class MyResolverInfo(nameserver.NameServer):
  def __init__(self, ip=MY_RESOLVER_IP):
    super(MyResolverInfo, self).__init__(ip=ip)

  def ClientIp(self):
    return self.GetMyResolverIpWithDuration()[0]


class GooglePublicDNS(nameserver.NameServer):
  def __init__(self, ip=GOOGLE_IP):
    super(GooglePublicDNS, self).__init__(ip=ip)

class SystemResolver(nameserver.NameServer):
  def __init__(self, ip=None):
    if not ip:
      ip = self._GetPrimaryIP()
    super(SystemResolver, self).__init__(ip=ip)

  def _GetPrimaryIP(self):
    internal = sys_nameservers.GetCurrentNameServers()
    if not internal:
      internal = sys_nameservers.GetAssignedNameServers()
    if not internal:
      print 'Odd - no built-in nameservers found.'
      return None
    else:
      return internal[0]
    return None

  def GetNetworkDataForIp(self, ip):
    class_c = addr_util.GetNetworkForIp(ip, reverse=True)
    host = '%s.origin.asn.cymru.com.' % class_c
    answer = self.GetTxtRecordWithDuration(host)
    return answer[0].split(' | ')

  def GetAsnForIp(self, ip):
    return self.GetNetworkDataForIp(ip)[0]

  def GetMyAsn(self):
    ip = MyResolverInfo().ClientIp()
    return self.GetAsnForIp(ip)


if __name__ == '__main__':
  print OpenDNS().InterceptionStateWithDuration()
  print MyResolverInfo().ClientIp()
  print SystemResolver().GetAsnForIp(MyResolverInfo().ClientIp())
