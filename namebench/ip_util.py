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

"""Utility functions related to IP Addresses & Hostnames."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import re
import sys
import zlib

if __name__ == "__main__":
  sys.path.append('../../third_party')

# Python 3.2 comes with ipaddress. Fall back to ipaddr.
try:
  import ipaddress
  IP = ipaddress.ip_address
  IP_NETWORK = ipaddress.ip_network
except ImportError:
  from ipaddr import ipaddr
  IP = ipaddr.IPAddress
  IP_NETWORK = ipaddr.IPNetwork


def extract_ips(ip_string):
  """Return a tuple of ip addressed held in a string.

  >>> extract_ips('127.0.0.1 8.8.8.8')
  [IPv4Address('127.0.0.1'), IPv4Address('8.8.8.8')]

  >>> extract_ips('127.0.0.1 ::1 8.8.8.8 2001:DB8::1')
  ['::1', '2001:DB8::1', IPv4Address('127.0.0.1'), IPv4Address('8.8.8.8')]
  """
  ips = []
  # IPV6 If this regexp is too loose, see Regexp-IPv6 in CPAN for inspiration.
  ips.extend(re.findall('[\dabcdef:]+:[\dabcdef:]+', ip_string, re.IGNORECASE))
  for ip in re.findall('\d+\.\d+\.\d+\.+\d+', ip_string):
    ips.append(IP(ip))
  return ips


def mask_string_with_ips(string):
  """Mask all private IP addresses listed in a string.

  >>> mask_string_with_ips('10.0.1.40 192.168.1.1')
  '10.0.x.x-9470 192.168.x.x-5663'

  >>> mask_string_with_ips('8.8.8.8 75.75.75.75')
  '8.8.8.8 75.75.75.75'
  """
  for ip in extract_ips(string):
    if ip.is_private:
      string = string.replace(str(ip), mask_ip(ip))
  return string


def mask_ip(ip):
  """Return an IP with half the bits replaced with a checksum.

  >>> mask_ip(IP('10.1.10.25'))
  '10.1.x.x-6985'

  >>> mask_ip(IP('3ffe:1900:4545:3:200:f8ff:fe21:67cf'))
  '3ffe:1900:4545:3::xx:8135'

  >>> mask_ip(IP('fe80::200:f8ff:fe21:67cf'))
  'fe80::200:f8ff::xx:1119'
  """
  if sys.version_info.major <= 2:
    ip_bytes = bytes(str(ip))
  else:
    ip_bytes = bytes(str(ip), 'ascii')

  checksum = zlib.crc32(ip_bytes) & 0xffffffff
  if ip.version == 6:
    prefix = ':'.join(str(ip).split(':')[:4])
    return prefix + '::xx:%s' % str(checksum)[-4:]
  else:
    prefix = '.'.join(str(ip).split('.')[:2])
    return prefix + '.x.x-%s' % str(checksum)[-4:]


if __name__ == "__main__":
    import doctest
    doctest.testmod()
