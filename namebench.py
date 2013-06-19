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
if sys.version < '2.7':
  your_version = sys.version.split(' ')[0]
  print('* The version of Python on your system is very old (%s). Please upgrade to 2.7 or higher.')
  sys.exit(1)
elif sys.version >= '3.0':
  print('* namebench is currently incompatible with Python 3.0 - trying anyways')

from namebench.ui import cli
from namebench.client import config

if __name__ == '__main__':
  options = config.GetMergedConfiguration()
  use_tk = False

  if len(sys.argv) == 1:
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
    # Workaround for unicode path errors.
    # See http://code.google.com/p/namebench/issues/detail?id=41
    if hasattr(sys, 'winver') and hasattr(sys, 'frozen'):
      os.environ['TCL_LIBRARY'] = os.path.join(os.path.dirname(sys.executable), 'tcl', 'tcl8.5')
      os.environ['TK_LIBRARY'] = os.path.join(os.path.dirname(sys.executable), 'tcl', 'tk8.5')
    try:
      import tkinter
    except ImportError:
      try:
        import _tkinter
      except ImportError:
        if len(sys.argv) == 1:
          print("- The python-tk (tkinter) library is missing, using the command-line interface.\n")
        use_tk = False

  if use_tk:
    print('Starting graphical interface for namebench (use -x to force command-line usage)')
    from namebench.ui import tk
    interface = tk.NameBenchGui
  else:
    interface = cli.NameBenchCli

  namebench = interface(options)
  namebench.Execute()

