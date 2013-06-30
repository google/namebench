#!/usr/bin/env python
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

"""Module for all nameserver related activity."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import random
import re
import socket
import sys
import time

# external dependencies (from nb_third_party)
import dns.exception
import dns.message
import dns.name
import dns.query
import dns.rcode
import dns.rdataclass
import dns.rdatatype
import dns.resolver
import dns.reversename
import dns.version

from . import health_checks
from . import provider_extensions
from . import addr_util
from . import util

# Look for buggy system versions of namebench
if dns.version.hexversion < 17301744:
  raise ValueError('dnspython 1.8.0+ required, while only %s was found. The '
                   'namebench source bundles 1.8.0, so use it.' % dns.version.version)



# How many failures before we disable system nameservers
MAX_NORMAL_FAILURES = 2
MAX_KEEPER_FAILURES = 8
MAX_WARNINGS = 10
FAILURE_PRONE_RATE = 10

# In order of most likely to be important.
PROVIDER_TAGS = ['isp', 'network', 'likely-isp', 'dhcp']

# EVIL IMPORT-TIME SIDE EFFECT
BEST_TIMER_FUNCTION = util.GetMostAccurateTimerFunction()


def ResponseToAscii(response):
  if not response:
    return None
  if response.answer:
    answers = [', '.join(map(str, x.items)) for x in response.answer]
    return ' -> '.join(answers).rstrip('"').lstrip('"')
  else:
    return dns.rcode.to_text(response.rcode())


class BrokenSystemClock(Exception):
  """Used if we detect errors with the system clock."""
  def __init__(self, value):
    self.value = value

  def __str__(self):
    return repr(self.value)


class NameServer(health_checks.NameServerHealthChecks, provider_extensions.NameServerProvider):
  """Hold information about a particular nameserver."""

  def __init__(self, ip, hostname=None, name=None, tags=None, provider=None,
               instance=None, location=None, latitude=None, longitude=None, asn=None,
               network_owner=None, dhcp_position=None, system_position=None):
    self.ip = ip
    self.name = name
    self.dhcp_position = dhcp_position
    self.system_position = system_position

    if tags:
      self.tags = set(tags)
    else:
      self.tags = set()
    self.provider = provider
    self.instance = instance
    self.location = location

    if self.location:
      self.country_code = location.split('/')[0]
      self.tags.add('country_%s' % self.country_code.lower())
    else:
      self.country_code = None

    self.latitude = latitude
    self.longitude = longitude
    self.asn = asn
    self.network_owner = network_owner
    self._hostname = hostname

    self.timeout = 5
    self.health_timeout = 5
    self.ping_timeout = 1
    self.ResetTestStatus()
    self._version = None
    self._node_ids = set()

    self.timer = BEST_TIMER_FUNCTION

    if ':' in self.ip:
      self.tags.add('ipv6')
    elif '.' in self.ip:
      self.tags.add('ipv4')

    if self.dhcp_position is not None:
      self.tags.add('dhcp')
    if self.system_position is not None:
      self.tags.add('system')

    if ip.endswith('.0') or ip.endswith('.255'):
      self.DisableWithMessage("IP appears to be a broadcast address.")
    elif self.is_bad:
      self.DisableWithMessage("Known bad address.")

  def AddNetworkTags(self, domain, provider, asn, country_code):
    if self.hostname:
      my_domain = addr_util.GetDomainFromHostname(self.hostname)
      hostname = self.hostname.lower()
    else:
      my_domain = 'UNKNOWN'
      hostname = ''
    if provider:
      provider = provider.lower()

    if domain and my_domain == domain:
      self.tags.add('isp')
    if asn and self.asn == asn:
      self.tags.add('network')

      if provider and 'isp' not in self.tags:
        if (provider in self.name.lower() or provider in self.hostname.lower()
            or (self.network_owner and provider in self.network_owner.lower())):
          self.tags.add('isp')
    elif provider and self.country_code == country_code and my_domain != domain:
      if (provider in self.name.lower() or provider in hostname
        or (self.network_owner and provider in self.network_owner.lower())):
        self.tags.add('likely-isp')

  def ResetTestStatus(self):
    """Reset testing status of this host."""
    self.warnings = set()
    self.shared_with = set()
    if self.is_disabled:
      self.tags.remove('disabled')
    self.checks = []
    self.failed_test_count = 0
    self.share_check_count = 0
    self.cache_checks = []
    self.is_slower_replica = False
    self.cdn_ping_max = 0
    self.cdn_ping_min = 65535
    self.cdn_ping_avg = 0
    self.ResetErrorCounts()

  def ResetErrorCounts(self):
    """NOTE: This gets called by benchmark.Run()!"""

    self.request_count = 0
    self.failure_count = 0
    self.error_map = {}

  @property
  def is_keeper(self):
    return bool(self.MatchesTags(['preferred', 'dhcp', 'system', 'specified']))

  @property
  def is_bad(self):
    if not self.is_keeper and self.MatchesTags(['rejected', 'blacklist']):
      return True

  @property
  def is_hidden(self):
    return self.HasTag('hidden')

  @property
  def is_disabled(self):
    return self.HasTag('disabled')

  @property
  def check_average(self):
    # If we only have a ping result, sort by it. Otherwise, use all non-ping results.
    if len(self.checks) == 1:
      return self.checks[0][3]
    else:
      return util.CalculateListAverage([x[3] for x in self.checks[1:]])

  @property
  def fastest_check_duration(self):
    if self.checks:
      return min([x[3] for x in self.checks])
    else:
      return 0.0

  @property
  def check_duration(self):
    return sum([x[3] for x in self.checks])

  @property
  def warnings_string(self):
    if self.is_disabled:
      return 'DISABLED: %s' % self.disabled_msg
    else:
      return ', '.join(map(str, self.warnings))

  @property
  def errors(self):
    return ['%s (%s requests)' % (_[0], _[1]) for _ in list(self.error_map.items()) if _[0] != 'Timeout']

  @property
  def error_count(self):
    return sum([_[1] for _ in list(self.error_map.items()) if _[0] != 'Timeout'])

  @property
  def timeout_count(self):
    return self.error_map.get('Timeout', 0)

  @property
  def notes(self):
    """Return a list of notes about this nameserver object."""
    my_notes = []
    if self.system_position == 0:
      my_notes.append('The current preferred DNS server')
    elif self.system_position:
      my_notes.append('A backup DNS server for this system')
    if self.dhcp_position is not None:
      my_notes.append('Assigned by your network DHCP server')
    if self.is_failure_prone:
      my_notes.append('%s of %s queries failed' % (self.failure_count, self.request_count))
    if self.HasTag('blacklist'):
      my_notes.append('BEWARE: IP appears in DNS server blacklist')
    if self.is_disabled:
      my_notes.append(self.disabled_msg)
    else:
      my_notes.extend(self.warnings)
    if self.errors:
      my_notes.extend(self.errors)
    return my_notes

  @property
  def hostname(self):
    if self._hostname is None and not self.is_disabled:
      self.UpdateHostname()
    return self._hostname

  def UpdateHostname(self):
    if not self.is_disabled:
      self._hostname = self.GetReverseIp(self.ip)
    return self._hostname

  @property
  def version(self):
    if self._version is None and not self.is_disabled:
      self.GetVersion()

    if not self._version:
      return None

    # Only return meaningful data
    if (re.search('\d', self._version) or
        (re.search('recursive|ns|server|bind|unbound', self._version, re.I)
         and 'ontact' not in self._version and '...' not in self._version)):
      return self._version
    else:
      return None

  @property
  def external_ips(self):
    """Return a set of external ips seen on this system."""
    # We use a slightly different pattern here because we want to
    # append to our results each time this is called.
    self._external_ips.add(self.GetMyResolverInfoWithDuration())
    # Only return non-blank entries
    return [x for x in self._external_ips if x]

  @property
  def node_ids(self):
    """Return a set of node_ids seen on this system."""
    if self.is_disabled:
      return []
    # Only return non-blank entries
    return [x for x in self._node_ids if x]

  def UpdateNodeIds(self):
    node_id = self.GetNodeIdWithDuration()[0]
    self._node_ids.add(node_id)
    return node_id

  @property
  def partial_node_ids(self):
    partials = []
    for node_id in self._node_ids:
      node_bits = node_id.split('.')
      if len(node_bits) >= 3:
        partials.append('.'.join(node_bits[0:-2]))
      else:
        partials.append('.'.join(node_bits))
    return partials

  @property
  def name_and_node(self):
    if self.node_ids:
      return '%s [%s]' % (self.name, ', '.join(self.partial_node_ids))
    else:
      return self.name

  @property
  def is_failure_prone(self):
    if self.failure_rate >= FAILURE_PRONE_RATE:
      return True
    else:
      return False

  @property
  def failure_rate(self):
    if not self.failure_count or not self.request_count:
      return 0
    else:
      return (float(self.failure_count) / float(self.request_count)) * 100

  def __str__(self):
    return '%s [%s:%s]' % (self.name, self.ip, ','.join(self.tags))

  def __repr__(self):
    return self.__str__()

  def HasTag(self, tag):
    """Matches one tag."""
    return tag in self.tags

  def MatchesTags(self, tags):
    """Matches many tags."""
    return self.tags.intersection(tags)

  def AddFailure(self, message, fatal=False):
    """Add a failure for this nameserver. This will effectively disable it's use."""

    respect_fatal = True
    if self.is_keeper:
      max_count = MAX_KEEPER_FAILURES
    else:
      max_count = MAX_NORMAL_FAILURES

    self.failed_test_count += 1
    if self.is_keeper:
      respect_fatal = False
      # Be quiet if this is simply a 'preferred' ipv6 host.
      if self.HasTag('preferred') and self.HasTag('ipv6') and len(self.checks) <= 1:
        self.tags.add('disabled')
      else:
        print(("\n* %s failed test #%s/%s: %s" % (self, self.failed_test_count, max_count, message)))

    if fatal and respect_fatal:
      self.DisableWithMessage(message)
    elif self.failed_test_count >= max_count:
      self.DisableWithMessage("Failed %s tests, last: %s" % (self.failed_test_count, message))

  def AddWarning(self, message, penalty=True):
    """Add a warning to a host."""

    if not isinstance(message, str):
      print(("Tried to add %s to %s (not a string)" % (message, self)))
      return None

    self.warnings.add(message)
    if penalty and len(self.warnings) >= MAX_WARNINGS:
      self.AddFailure('Too many warnings (%s), probably broken.' % len(self.warnings), fatal=True)

  def DisableWithMessage(self, message):
    self.tags.add('disabled')
    if self.is_keeper and not self.HasTag('ipv6'):
      print(("\nDISABLING %s: %s\n" % (self, message)))
    else:
      self.tags.add('hidden')
    self.disabled_msg = message

  def CreateRequest(self, record, request_type, return_type):
    """Function to work around any dnspython make_query quirks."""
    return dns.message.make_query(record, request_type, return_type)

  def Query(self, request, timeout):
#    print "%s -> %s" % (request, self)
    return dns.query.udp(request, self.ip, timeout, 53)

  def TimedRequest(self, type_string, record_string, timeout=None, rdataclass=None):
    """Make a DNS Get, returning the reply and duration it took.

    Args:
      type_string: DNS record type to query (string)
      record_string: DNS record name to query (string)
      timeout: optional timeout (float)
      rdataclass: optional result class (defaults to rdataclass.IN)

    Returns:
      A tuple of (response, duration in ms [float], error_msg)

    In the case of a DNS response timeout, the response object will be None.
    """
    if not rdataclass:
      rdataclass = dns.rdataclass.IN
    else:
      rdataclass = dns.rdataclass.from_text(rdataclass)

    request_type = dns.rdatatype.from_text(type_string)
    record = dns.name.from_text(record_string, None)
    request = None
    self.request_count += 1

    try:
      request = self.CreateRequest(record, request_type, rdataclass)
    except ValueError:
      if not request:
        return (None, 0, util.GetLastExceptionString())

    if not timeout:
      timeout = self.timeout

    error_msg = None
    exc = None
    duration = None
    try:
      start_time = self.timer()
      response = self.Query(request, timeout)
      duration = self.timer() - start_time
    except (dns.exception.Timeout) as exc:
      response = None
    except (dns.query.BadResponse, dns.message.TrailingJunk,
            dns.query.UnexpectedSource) as exc:
      error_msg = util.GetLastExceptionString()
      response = None
    # This is pretty normal if someone runs namebench offline.
    except socket.error:
      response = None
      if ':' in self.ip:
        error_msg = 'socket error: IPv6 may not be available.'
      else:
        error_msg = util.GetLastExceptionString()
    # Pass these exceptions up the food chain
    except (KeyboardInterrupt, SystemExit, SystemError) as exc:
      raise exc
    except:
      error_msg = util.GetLastExceptionString()
      print(("* Unusual error with %s:%s on %s: %s" % (type_string, record_string, self, error_msg)))
      response = None

    if not response:
      self.failure_count += 1

    if not duration:
      duration = self.timer() - start_time

    if exc and not error_msg:
      error_msg = '%s: %s' % (record_string, util.GetLastExceptionString())

    if error_msg:
      key = util.GetLastExceptionString()
      self.error_map[key] = self.error_map.setdefault(key, 0) + 1

    if duration < 0:
      raise BrokenSystemClock('The time on your machine appears to be going backwards. '
                              'We cannot accurately benchmark due to this error. '
                              '(timer=%s, duration=%s)' % (self.timer, duration))
    return (response, util.SecondsToMilliseconds(duration), error_msg)

  def GetVersion(self):
    version = ''
    (response, duration, _) = self.TimedRequest('TXT', 'version.bind.', rdataclass='CHAOS',
                                                        timeout=self.health_timeout)
    if response and response.answer:
      response_string = ResponseToAscii(response)
      version = response_string

    self._version = version
    return (self._version, duration)

  def GetReverseIp(self, ip, retries_left=2):
    """Request a hostname for a given IP address."""
    try:
      print(("reverse: %s -> %s" % (ip, self)))
      answer = dns.resolver.query(dns.reversename.from_address(ip), 'PTR')
    except dns.resolver.NXDOMAIN:
      return ip
    except:
      if retries_left:
        print(("* Failed to get hostname for %s (retries left: %s): %s" % (ip, retries_left, util.GetLastExceptionString())))
        return self.GetReverseIp(ip, retries_left=retries_left-1)
      else:
        return ip

    if answer:
      return answer[0].to_text().rstrip('.')
    else:
      return ip

  def GetTxtRecordWithDuration(self, record, retries_left=2):
    (response, duration, _) = self.TimedRequest('TXT', record, timeout=self.health_timeout)
    if response and response.answer:
      return (response.answer[0].items[0].to_text().lstrip('"').rstrip('"'), duration)
    elif not response and retries_left:
      print(("* Failed to lookup %s (retries left: %s): %s" % (record, retries_left, util.GetLastExceptionString())))
      return self.GetTxtRecordWithDuration(record, retries_left=retries_left-1)
    else:
      return (None, duration)

  def GetIpFromNameWithDuration(self, name):
    """Get an IP for a given name with a duration."""
    (response, duration, _) = self.TimedRequest('A', name, timeout=self.health_timeout)
    if response and response.answer:
      ip = response.answer[0].items[0].to_text()
      return (ip, duration)
    else:
      return (None, duration)

  def GetNameFromNameWithDuration(self, name):
    """Get a name from another name (with duration). Used for node id lookups."""
    (ip, duration) = self.GetIpFromNameWithDuration(name)
    if ip:
      return (self.GetReverseIp(ip), duration)
    else:
      return (None, duration)

  def GetNodeIdWithDuration(self):
    """Try to determine the node id for this nameserver (tries many methods)."""
    node = ''

    if self.hostname.endswith('ultradns.net') or self.ip.startswith('156.154.7'):
      (node, duration) = self.GetUltraDnsNodeWithDuration()
    elif self.ip.startswith('8.8'):
      (node, duration) = self.GetMyResolverHostNameWithDuration()
    elif self.hostname.endswith('opendns.com') or self.ip.startswith('208.67.22'):
      (node, duration) = self.GetOpenDnsNodeWithDuration()
    else:
      (response, duration, _) = self.TimedRequest('TXT', 'hostname.bind.', rdataclass='CHAOS')
      if not response or not response.answer:
        (response, duration, _) = self.TimedRequest('TXT', 'id.server.', rdataclass='CHAOS')
      if response and response.answer:
        node = ResponseToAscii(response)

    return (node, duration)

  def DistanceFromCoordinates(self, lat, lon):
    """In km."""
    if self.latitude:
      return util.DistanceBetweenCoordinates(float(lat), float(lon), float(self.latitude), float(self.longitude))
    else:
      return None

if __name__ == '__main__':
  ns = NameServer(sys.argv[1])
  print(("-" * 64))
  print(("IP:      %s" % ns.ip))
  print(("Host:    %s" % ns.hostname))
  print(("Version: %s" % ns.version))
  print(("Node:    %s" % ns.node_ids))
