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

import datetime
import math
import os.path
import sys
import tempfile


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
  """Split a list.

  Args:
    seq: sequence
    size: int

  Returns:
    New list.

  Recipe From http://code.activestate.com/recipes/425397/ (Modified to not return blank values)
  """
  newseq = []
  splitsize = 1.0/size*len(seq)
  for i in range(size):
    newseq.append(seq[int(round(i*splitsize)):int(round((i+1)*splitsize))])

  return  [x for x in newseq if x]


def FindDataFile(filename):
  """Find a datafile, searching various relative and OS paths."""
  filename = os.path.expanduser(filename)
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
  for directory in reversed(sys.path):
    other_places.append(directory)
    other_places.append(os.path.join(directory, 'namebench'))

  for place in other_places:
    path = os.path.join(place, filename)
    if os.path.exists(path):
      return path

  print 'I could not find "%s". Tried:' % filename
  for path in other_places:
    print '  %s' % path
  return filename

def GenerateOutputFilename(extension):
  """Generate a decent default output filename for a given extensio."""

  # used for resolv.conf
  if '.' in extension:
    filename = extension
  else:
    output_base = 'namebench_%s' % datetime.datetime.strftime(datetime.datetime.now(),
                                                              '%Y-%m-%d %H%M')
    output_base = output_base.replace(':', '').replace(' ', '_')
    filename = '.'.join((output_base, extension))

  output_dir = tempfile.gettempdir()
  return os.path.join(output_dir, filename)
    


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
