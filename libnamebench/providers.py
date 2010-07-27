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

import re
import socket
import sys

if __name__ == '__main__':
  sys.path.append('..')
  import nb_third_party

import addr_util
import util
import nameserver
import sys_nameservers

OPENDNS_IP = '208.67.220.220'
GOOGLE_IP = '8.8.8.8'
MY_RESOLVER_HOST = 'ns2.myresolver.info.'
ULTRADNS_AUTH_IP = '204.69.234.1'


def GetExternalIp():
  """Helper method to get external IP from anyone who cares."""
  for provider in (UltraDNSAuth(), MyResolverInfo()):
    answer = provider.GetClientIp()
    if answer:
      return answer

class OpenDNS(nameserver.NameServer):
  
  """Any OpenDNS specific functions."""
  
  def __init__(self, ip=OPENDNS_IP):
    super(OpenDNS, self).__init__(ip=ip)

  def InterceptionStateWithDuration(self):
    return self.GetOpenDnsInterceptionStateWithDuration()


class UltraDNSAuth(nameserver.NameServer):

  """Any UltraDNS authhoritative specific functions."""

  def __init__(self, ip=ULTRADNS_AUTH_IP):
    super(UltraDNSAuth, self).__init__(ip=ip)

  def GetClientIp(self):
    return self.GetIpFromNameWithDuration('whoami.ultradns.net.')[0]


class MyResolverInfo(nameserver.NameServer):
  def __init__(self, ip=None):
    if not ip:
      try:
        ip = socket.gethostbyname(MY_RESOLVER_HOST)
      except:
        print "Could not resolve %s: %s" % (MY_RESOLVER_HOST, util.GetLastExceptionString())
        # TODO(tstromberg): Find a more elegant fallback solution.
        ip = '127.0.0.1'
           
    super(MyResolverInfo, self).__init__(ip=ip)

  def GetClientIp(self):
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
    if answer and answer[0] and '|' in answer[0]:
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
