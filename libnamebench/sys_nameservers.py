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

"""Methods to get information about system DNS servers."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import glob
import os
import subprocess
import sys
import time

if __name__ == '__main__':
  sys.path.append('../nb_third_party')

# 3rd party libraries
import dns.resolver

# local libs
import addr_util

MAX_LEASE_AGE = 24 * 3600
MIN_LEASE_FILE_SIZE = 1024

def GetAllSystemNameServers():
  servers = list(set(GetCurrentNameServers() + GetAssignedNameServers()))
  print servers
  return servers

def GetCurrentNameServers():
  """Return list of DNS server IP's used by the host via dnspython"""
  try:
    servers = dns.resolver.Resolver().nameservers
  except:
    print "Unable to get list of internal DNS servers."
    servers = []

  # dnspython does not always get things right on Windows, particularly in
  # versions with right-to-left languages. Fall back to ipconfig /all
  if not servers and sys.platform[:3] == 'win':
    return _GetNameServersFromWinIpConfig()
  return servers

def GetAssignedNameServers():
  """Servers assigned by DHCP."""
  if sys.platform == 'darwin':
    return _GetNameServersFromMacIpConfig()
  else:
    return _GetNameServersFromDhclient()

def _GetNameServersFromMacIpConfig():
  servers = []
  ifcount = subprocess.Popen(['ipconfig', 'ifcount'], stdout=subprocess.PIPE).stdout.read()
  interfaces = ["en%s" % (int(x)-1) for x in range(int(ifcount))]
  for iface in interfaces:
    output = subprocess.Popen(['ipconfig', 'getpacket', iface], stdout=subprocess.PIPE).stdout.read()
    for line in output.split('\n'):
      if 'domain_name_server' in line:
#        print "%s domain_name_server: %s" % (iface, line)
        servers.extend(addr_util.ExtractIPsFromString(line))
  return servers


def _GetNameServersFromWinIpConfig():
  """Return a list of DNS servers via ipconfig (Windows only)"""
  servers = []
  output = subprocess.Popen(['ipconfig', '/all'], stdout=subprocess.PIPE).stdout.read()
  for line in output.split('\r\n'):
    if 'DNS Servers' in line:
      print "ipconfig: %s" % line
      servers.extend(addr_util.ExtractIPsFromString(line))
  return servers

def _GetNameServersFromDhclient():
  path = _FindNewestDhclientLeaseFile()
  if not path:
    return []

  # We want the last matching line in the file
  for line in open(path):
    if 'option domain-name-servers' in line:
      ns_string = line

  if ns_string:
    return addr_util.ExtractIPsFromString(ns_string)
  else:
    return []

def _FindNewestDhclientLeaseFile():
  paths = [
      '/var/lib/dhcp3/dhclient.*leases'
  ]

  found = []
  for path in paths:
    for filename in glob.glob(path):
      if os.path.getsize(filename) < MIN_LEASE_FILE_SIZE:
        continue
      elif time.time() - os.path.getmtime(filename) > MAX_LEASE_AGE:
        continue
      else:
        try:
          fp = open(filename, 'rb')
          fp.close()
          found.append(filename)
        except:
          continue

  if found:
    return sorted(found, key=os.path.getmtime)[-1]
  else:
    return None

if __name__ == '__main__':
  print "Current: %s" % GetCurrentNameServers()
  print "Assigned: %s" % GetAssignedNameServers()
  print "System: %s" % GetAllSystemNameServers()
