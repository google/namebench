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


"""Simple DNS server comparison benchmarking tool.

Designed to assist system administrators in selection and prioritization.
"""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

VERSION = '0.9.2'

import os
import sys
import platform

# Check before we start importing internal dependencies
if sys.version < '2.4':
  your_version = sys.version.split(' ')[0]
  print '* Your Python version (%s) is too old! Please upgrade to 2.6+!' % your_version
  sys.exit(1)
elif sys.version >= '3.0':
  print '* namebench is currently incompatible with Python 3.0 - trying anyways'

# See if a third_party library exists -- use it if so.
try:
  import third_party
except ImportError:
  pass


from libnamebench import cli
from libnamebench import config

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
    print '- Will try to use Tk GUI'
    try:
      import Tkinter
    except ImportError:
      print '- Python TK libraries are unavailable (please install for a proper GUI)'
      use_tk = False

  if use_tk:
    from libnamebench import tk
    interface = tk.NameBenchGui
  else:
    interface = cli.NameBenchCli

  namebench = interface(options, supplied_ns, global_ns, regional_ns, version=VERSION)
  namebench.Execute()

