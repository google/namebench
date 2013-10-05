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

# TODO(tstromberg): Investigate replacement with ipaddr library

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import re
import zlib

# TODO(tstromberg): Find a way to combine the following two regexps.

# Used to decide whether or not to benchmark a name
INTERNAL_RE = re.compile('^0|\.pro[md]z*\.|\.corp|\.bor|\.hot$|internal|dmz|'
                         '\._[ut][dc]p\.|intra|\.\w$|\.\w{5,}$', re.IGNORECASE)

# Used to decide if a hostname should be censored later.
PRIVATE_RE = re.compile('^\w+dc\.|^\w+ds\.|^\w+sv\.|^\w+nt\.|\.corp|internal|'
                        'intranet|\.local', re.IGNORECASE)

# ^.*[\w-]+\.[\w-]+\.[\w-]+\.[a-zA-Z]+\.$|^[\w-]+\.[\w-]{3,}\.[a-zA-Z]+\.$
FQDN_RE = re.compile('^.*\..*\..*\..*\.$|^.*\.[\w-]*\.\w{3,4}\.$|^[\w-]+\.[\w-]{4,}\.\w+\.')

IP_RE = re.compile('^[0-9.]+$')


def ExtractIPsFromString(ip_string):
  """Return a tuple of ip addressed held in a string."""

  ips = []
  # IPV6 If this regexp is too loose, see Regexp-IPv6 in CPAN for inspiration.
  ips.extend(re.findall('[\dabcdef:]+:[\dabcdef:]+', ip_string, re.IGNORECASE))
  ips.extend(re.findall('\d+\.\d+\.\d+\.+\d+', ip_string))
  return ips


def ExtractIPTuplesFromString(ip_string):
  """Return a list of (ip, name) tuples for use by NameServer class."""
  ip_tuples = []
  for ip in ExtractIPsFromString(ip_string):
    ip_tuples.append((ip, ip))
  return ip_tuples


def IsPrivateHostname(hostname):
  """Basic matching to determine if the hostname is likely to be 'internal'."""
  if PRIVATE_RE.search(hostname):
    return True
  else:
    return False


def IsLoopbackIP(ip):
  """Boolean check to see if an IP is private or not.

  Args:
    ip: str

  Returns:
    Boolean
  """
  if ip.startswith('127.') or ip == '::1':
    return True
  else:
    return False


def IsPrivateIP(ip):
  """Boolean check to see if an IP is private or not.

  Args:
    ip: str

  Returns:
    Number of bits that should be preserved (int, or None)
  """
  if re.match('^10\.', ip):
    return 1
  elif re.match('^192\.168', ip):
    return 2
  elif re.match('^172\.(1[6-9]|2[0-9]|3[0-1])\.', ip):
    return 1
  else:
    return None

def MaskStringWithIPs(string):
  """Mask all private IP addresses listed in a string."""
  
  ips = ExtractIPsFromString(string)
  for ip in ips:
    use_bits = IsPrivateIP(ip)
    if use_bits:
      masked_ip = MaskIPBits(ip, use_bits)
      string = string.replace(ip, masked_ip)
  return string
    
def MaskIPBits(ip, use_bits):
  """Mask an IP, but still keep a meaningful checksum."""
  ip_parts = ip.split('.')
  checksum = zlib.crc32(''.join(ip_parts[use_bits:]))
  masked_ip = '.'.join(ip_parts[0:use_bits])
  return masked_ip + '.x-' + str(checksum)[-4:]


def MaskPrivateHost(ip, hostname, name):
  """Mask unnamed private IP's."""

  # If we have a name not listed as SYS-x.x.x.x, then we're clear.
  if name and ip not in name:
    # Even if we are listed (Internal 192-0-1 for instance), data can leak via hostname.
    if IsPrivateIP(ip):
      hostname = 'internal.ip'
    return (ip, hostname, name)

  use_bits = IsPrivateIP(ip)
  if use_bits:
    masked_ip = MaskIPBits(ip, use_bits)
    masked_hostname = 'internal.ip'
  elif IsPrivateHostname(hostname):
    masked_ip = MaskIPBits(ip, 2)
    masked_hostname = 'internal.name'
  else:
    masked_ip = ip
    masked_hostname = hostname

  if 'SYS-' in name:
    masked_name = 'SYS-%s' % masked_ip
  else:
    masked_name = ''
  return (masked_ip, masked_hostname, masked_name)

if __name__ == '__main__':
  print MaskStringWithIPs('10.0.0.1 has a sharing relationship with 192.168.0.1 and 8.8.8.8')
