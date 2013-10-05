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

"""namebench: DNS service benchmarking tool."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'


import os
import platform
import sys

# Check before we start importing internal dependencies
if sys.version < '2.4':
  your_version = sys.version.split(' ')[0]
  print '* Your Python version (%s) is too old! Please upgrade to 2.6+!' % your_version
  sys.exit(1)
elif sys.version >= '3.0':
  print '* namebench is currently incompatible with Python 3.0 - trying anyways'

from libnamebench import cli
from libnamebench import config
from libnamebench import version

if __name__ == '__main__':
  (options, supplied_ns, global_ns, regional_ns) = config.GetConfiguration()
  use_tk = False

  if not options.no_gui:
    if os.getenv('DISPLAY', None):
      use_tk = True
    # Macs get a special Cocoa binary
    if os.getenv('I_LOVE_TK', None):
      use_tk = True
    elif platform.mac_ver()[0]:
      use_tk = False
    elif platform.system() == 'Windows':
      use_tk = True

  if use_tk:
    try:
      # Workaround for unicode path errors.
      # See http://code.google.com/p/namebench/issues/detail?id=41
      if hasattr(sys, 'winver') and hasattr(sys, 'frozen'):
        os.environ['TCL_LIBRARY'] = os.path.join(os.path.dirname(sys.executable), 'tcl', 'tcl8.5')
        os.environ['TK_LIBRARY'] = os.path.join(os.path.dirname(sys.executable), 'tcl', 'tk8.5')
      import Tkinter
    except ImportError:
      if len(sys.argv) == 1:
        print "- The python-tk (tkinter) library is missing, using the command-line interface.\n"
      use_tk = False

  if use_tk:
    print 'Starting Tk interface for namebench...'
    from libnamebench import tk
    interface = tk.NameBenchGui
  else:
    interface = cli.NameBenchCli

  namebench = interface(options, supplied_ns, global_ns, regional_ns, version=version.VERSION)
  namebench.Execute()

