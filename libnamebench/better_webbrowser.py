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
import traceback
import webbrowser

def create_win32_http_cmd(url):
  """Create a command-line tuple to launch a web browser for a given URL.
  
  At the moment, this ignores all default arguments to the browser.
  TODO(tstromberg): Properly parse the command-line arguments.
  """
  key = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER,
                        'Software\Classes\http\shell\open\command')
  cmd = _winreg.EnumValue(key, 0)[1]
  # "C:\blah blah\iexplore.exe" -nohome
  # "C:\blah blah\firefox.exe" -requestPending -osint -url "%1"  
  if '"' in cmd:
    executable = cmd.split('"')[1]
  else:
    executable = cmd.split(' ')[0]
    
  if not os.path.exists(executable):
    print "Default HTTP browser does not exist: %s" % executable
    return False
  else:
    print "HTTP handler: %s" % executable
  return (executable, url)


if sys.platform[:3] == 'win':
  import _winreg

  class WindowsHttpDefault(webbrowser.BaseBrowser):
    """Directly uses the Windows HTTP handler to open a web browser, which may
       be different than what os.startfile outputs for local HTML files."""

    def open(self, url, new=0, autoraise=1):
      command_args = create_win32_http_cmd(url)
      if not command_args:
        return False
    
      print command_args
      try:
        browser = subprocess.Popen(command_args)
      except:
        traceback.print_exc()
        print "* Failed to run HTTP handler, trying next browser."
        return False
        
  webbrowser.register("windows-http", WindowsHttpDefault, update_tryorder=-1)

def open(url):
  if hasattr(webbrowser, '_tryorder'):
    print "Browsers: %s" % webbrowser._tryorder
  print "Opening: %s" % url
  
  webbrowser.open(url)
