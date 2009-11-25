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

"""Wrapper for webbrowser library, to invoke the http handler on win32."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import os.path
import subprocess
import sys
import webbrowser

use_win32 = False
if sys.platform == "win32":
  try:
    import _winreg
    use_win32 = True
  except ImportError:
    pass
  

def open(url):
  """Open a URL in the users web browser."""

  if not use_win32:
    return webbrowser.open(url)
  else:
    return win32_open(url)

def win32_open(url):
  """Open a URL with the program handler for the http protocol on win32."""

  command_args = create_win32_http_cmd(url)
  browser = subprocess.Popen(command_args)
  
def get_win32_http_handler():
  """Given a url, return the appropriate win32 command and arguments."""

  key = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER,
                        'Software\Classes\http\shell\open\command')
  return _winreg.EnumValue(key, 0)[1]


def create_win32_http_cmd(url):
  """Create a command-line tuple to launch a web browser for a given URL.
  
  At the moment, this ignores all default arguments to the browser.
  TODO(tstromberg): Properly parse the command-line arguments.
  """

  cmd = get_win32_http_handler()
  # "C:\blah blah\iexplore.exe" -nohome
  # "C:\blah blah\firefox.exe" -requestPending -osint -url "%1"  
  if '"' in cmd:
    executable = cmd.split('"')[1]
  else:
    executable = cmd.split(' ')[0]
  return (executable, url)
