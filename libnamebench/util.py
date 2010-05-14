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
import re
import util
import os.path
import socket
import sys
import traceback
import zlib

# See if a third_party library exists -- use it if so.
try:
  import third_party
except ImportError:
  pass

import dns.resolver

import nameserver

def CalculateListAverage(values):
  """Computes the arithmetic mean of a list of numbers."""
  if not values:
    return 0
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


def SecondsToMilliseconds(seconds):
  return seconds * 1000

def SplitSequence(seq, size):
  """Recipe From http://code.activestate.com/recipes/425397/

  Modified to not return blank values."""
  newseq = []
  splitsize = 1.0/size*len(seq)
  for i in range(size):
    newseq.append(seq[int(round(i*splitsize)):int(round((i+1)*splitsize))])

  return  [ x for x in newseq if x ]
  
def InternalNameServers():
  """Return list of DNS server IP's used by the host."""
  try:
    return dns.resolver.Resolver().nameservers
  except:
    print "Unable to get list of internal DNS servers."
    return []

def ExtractIPsFromString(ip_string):
  """Return a tuple of ip addressed held in a string."""

  ips = []
  # IPV6 If this regexp is too loose, see Regexp-IPv6 in CPAN for inspiration.
  ips.extend(re.findall('[\dabcdef:]+:[\dabcdef:]+', ip_string, re.IGNORECASE))
  ips.extend(re.findall('\d+\.\d+\.\d+\.+\d+', ip_string))
  return ips

def ExtractIPTuplesFromString(ip_string):
  ip_tuples = []
  for ip in ExtractIPsFromString(ip_string):
      ip_tuples.append((ip,ip))
  return ip_tuples

def IsPrivateHostname(hostname):
  """Basic matching to determine if the hostname is likely to be 'internal'."""
  if re.search('^\w+dc\.|^\w+ds\.|^\w+sv\.|^\w+nt\.|\.corp|internal|intranet|\.local', hostname, re.I):
    return True
  else:
    return False

def IsPrivateIP(ip):
  """Boolean check to see if an IP is private or not.
  
  Returns: Number of bits that should be preserved.
  """
  if re.match('^10\.', ip):
    return 1
  elif re.match('^192\.168', ip):
    return 2
  elif re.match('^172\.(1[6-9]|2[0-9]|3[0-1])\.', ip):
    return 1
  else:
    return None

def MaskIPBits(ip, use_bits):
  """Mask an IP, but still keep a meaningful checksum."""
  ip_parts = ip.split('.')
  checksum = zlib.crc32(''.join(ip_parts[use_bits:]))
  masked_ip = '.'.join(ip_parts[0:use_bits])
  return masked_ip + ".x-" + str(checksum)[-4:]

def MaskPrivateHost(ip, hostname, name):
  """Mask unnamed private IP's."""
  
  # If we have a name not listed as SYS-x.x.x.x, then we're clear.
  if name and ip not in name:
    return (ip, hostname, name)
  
  use_bits = IsPrivateIP(ip)
  if use_bits:
    ip = MaskIPBits(ip, use_bits)
    hostname = 'internal.ip'
  elif IsPrivateHostname(hostname):
    ip = MaskIPBits(ip, 2)
    hostname = 'internal.name'

  if 'SYS-' in name:
    name = "SYS-%s" % ip
  else:
    name = ''
  return (ip, hostname, name)
    
def FindDataFile(filename):
  if os.path.exists(filename):
    return filename

  # If it's not a relative path, we can't do anything useful.
  if os.path.isabs(filename):
    return filename

  other_places = [os.getcwd(),
                  os.path.join(os.path.dirname(os.path.dirname(sys.argv[0])), 'Contents', 'Resources'),
                  os.path.join(os.getcwd(), 'namebench.app', 'Contents', 'Resources'),
                  os.path.join(os.getcwd(), '..'),
                  os.path.join(sys.prefix, 'namebench'),
                  '/usr/local/share/namebench'
                  '/usr/local/etc/namebench',
                  '/usr/local/namebench',
                  '/etc/namebench',
                  '/usr/share/namebench',
                  '/usr/namebench']
  for dir in reversed(sys.path):
    other_places.append(dir)
    other_places.append(os.path.join(dir, 'namebench'))

  for place in other_places:
    path = os.path.join(place, filename)
    if os.path.exists(path):
      return path

  print "I could not find your beloved '%s'. Tried:" % filename
  for path in other_places:
    print "  %s" % path
  return filename

def GetLastExceptionString():
  """Get the last exception and return a good looking string for it."""
  (exc, error) = sys.exc_info()[0:2]
  exc_msg = str(exc)
  if '<class' in exc_msg:
    exc_msg = exc_msg.split("'")[1]

  exc_msg = exc_msg.replace('dns.exception.', '')
  error = '%s %s' % (exc_msg, error)
  # We need to remove the trailing space at some point.
  return error.rstrip()
