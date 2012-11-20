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

"""Utility functions for parsing hostnames."""

# TODO(tstromberg): Investigate replacement with ipaddr library

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import codecs
import re

# local
# TODO(tstromberg): Work around ValueError: Attempted relative import in non-package
import util


# Used to decide whether or not to benchmark a name
INTERNAL_RE = re.compile('^0|\.pro[md]z*\.|\.corp|\.bor|\.hot$|internal|dmz|'
                         '\._[ut][dc]p\.|intra|\.\w$|\.\w{5,}$', re.IGNORECASE)

# Used to decide if a hostname should be censored later.
PRIVATE_RE = re.compile('^\w+dc\.|^\w+ds\.|^\w+sv\.|^\w+nt\.|\.corp|internal|'
                        'intranet|\.local', re.IGNORECASE)

# ^.*[\w-]+\.[\w-]+\.[\w-]+\.[a-zA-Z]+\.$|^[\w-]+\.[\w-]{3,}\.[a-zA-Z]+\.$
FQDN_RE = re.compile('^.*\..*\..*\..*\.$|^.*\.[\w-]*\.\w{3,4}\.$|^[\w-]+\.[\w-]{4,}\.\w+\.')

_SUFFIX_RULES_PATH = util.FindDataFile('data/effective_tld_names.dat')
_LOADED_SUFFIX_RULES = set()
_LOADED_SUFFIX_EXCEPTIONS = set()


def _public_suffix_rules():
  """Return a tuple of cached public suffix rules and exceptions."""
  if not _LOADED_SUFFIX_RULES:
    for line in codecs.open(_SUFFIX_RULES_PATH, 'r', 'utf8'):
      line = line.strip()
      if not line or line.startswith('//'):
        continue
      elif line.startswith('!'):
        _LOADED_SUFFIX_EXCEPTIONS.add(line[1:])
        # Make sure exceptions can fall back even if omitted from the data
        _LOADED_SUFFIX_RULES.add(line[line.index('.')+1:])
      elif '*' in line:
        # Add the wildcard and the implied parent
        _LOADED_SUFFIX_RULES.add(line.replace('*', ''))
        _LOADED_SUFFIX_RULES.add(line.replace('*.', ''))
      else:
        _LOADED_SUFFIX_RULES.add(line.replace('*', ''))

  return (_LOADED_SUFFIX_RULES, _LOADED_SUFFIX_EXCEPTIONS)


def get_public_suffix(hostname):
  """Get the TLD or other type of public suffix for a given hostname.

  >>> get_public_suffix('www.demon.co.uk')
  u'co.uk'

  >>> get_public_suffix('.com.com')
  u'com'

  >>> get_public_suffix('x.ac.ar')  # Wildcard
  u'ac.ar'

  >>> get_public_suffix('nic.ar')  # Testing negative rule
  u'ar'

  >>> get_public_suffix('internal.polar')  # None

  >>> get_public_suffix('nic.py')  # Assumed suffix
  u'py'
  """
  answers = []
  rules, exceptions = _public_suffix_rules()
  for rule in rules:
    if rule.startswith('.') and hostname.endswith(rule):
      # turn www.demon.co.uk with a wildcard of *.uk into an answer of co.uk
      resolved_wildcard = hostname.replace(rule, '').split('.')[-1] + rule
      if resolved_wildcard not in _LOADED_SUFFIX_EXCEPTIONS:
        answers.append(resolved_wildcard)
    elif hostname.endswith('.' + rule):
      answers.append(rule)
  if answers:
    return max(answers, key=len)
  return None


def get_domain_name(hostname):
  """Get the domain part of a hostname.

  >>> get_domain_name('polar.internal')
  >>> get_domain_name('nic.py')
  u'nic.py'
  >>> get_domain_name('www.demon.co.uk')
  u'demon.co.uk'
  """
  suffix = get_public_suffix(hostname)
  if suffix:
    custom_part = hostname.replace(suffix, '').rstrip('.').split('.')[-1]
    return '.'.join([custom_part, suffix])
  return None


def get_provider_name(hostname):
  """Get the custom part of a hostname

  >>> get_provider_name('polar.internal')
  >>> get_provider_name('nic.py')
  u'nic'
  >>> get_provider_name('www.demon.co.uk')
  u'demon'
  >>> get_provider_name('dhcp-124012.western.lon.demon.co.uk')
  u'demon'
  """
  domain = get_domain_name(hostname)
  if domain:
    return domain.split('.')[0]
  return None


def is_private(hostname):
  """Guess if the hostname is 'internal' and should be filtered before sharing.

  >>> is_private('internal.rtci.com.')
  True
  >>> is_private('ntserver.corporate')
  True
  >>> is_private('www.google.com')
  False
  """
  if PRIVATE_RE.search(hostname):
    return True
  else:
    return False


if __name__ == "__main__":
    import doctest
    doctest.testmod()

