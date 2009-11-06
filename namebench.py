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
import platform
from lib import cli
from lib import config

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
      from lib import tk
      interface = tk.NameBenchGui
    except ImportError:
      print '- Python TK libraries are unavailable (please install for a proper GUI)'
      interface = cli.NameBenchCli
  else:
    interface = cli.NameBenchCli

  namebench = interface(options, supplied_ns, global_ns, regional_ns, version=VERSION)
  namebench.Execute()

