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

import util


def output(string):
  print string


def create_win32_http_cmd(url):
  """Create a command-line tuple to launch a web browser for a given URL.

  Args:
    url: string

  Returns:
    tuple of: (executable, arg1, arg2, ...)

  At the moment, this ignores all default arguments to the browser.
  TODO(tstromberg): Properly parse the command-line arguments.
  """
  browser_type = None
  try:
    key = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER,
                          'Software\Classes\http\shell\open\command')
    browser_type = 'user'
  except WindowsError:
    key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE,
                          'Software\Classes\http\shell\open\command')
    browser_type = 'machine'
  except:
    return False

  cmd = _winreg.EnumValue(key, 0)[1]
  # "C:\blah blah\iexplore.exe" -nohome
  # "C:\blah blah\firefox.exe" -requestPending -osint -url "%1"
  if '"' in cmd:
    executable = cmd.split('"')[1]
  else:
    executable = cmd.split(' ')[0]

  if not os.path.exists(executable):
    output('$ Default HTTP browser does not exist: %s' % executable)
    return False
  else:
    output('$ %s HTTP handler: %s' % (browser_type, executable))
  return (executable, url)


def open(url):
  """Opens a URL, overriding the normal webbrowser.open methods for sanity."""

  try:
    webbrowser.open(url, new=1, autoraise=True)
  # If the user is missing the osascript binary - see
  # http://code.google.com/p/namebench/issues/detail?id=88
  except:
    output('Failed to open: [%s]: %s' % (url, util.GetLastExceptionString()))
    if os.path.exists('/usr/bin/open'):
      try:
        output('trying open: %s' % url)
        p = subprocess.Popen(('open', url))
        p.wait()
      except:
        output('open did not seem to work: %s' % util.GetLastExceptionString())
    elif sys.platform[:3] == 'win':
      try:
        output('trying default Windows controller: %s' % url)
        controller = webbrowser.get('windows-default')
        controller.open_new(url)
      except:
        output('WindowsController did not work: %s' % util.GetLastExceptionString())


# *NOTE*: EVIL IMPORT SIDE EFFECTS AHEAD!
#
# If we are running on Windows, register the WindowsHttpDefault class.
if sys.platform[:3] == 'win':
  import _winreg
  
  # We don't want to load this class by default, because Python 2.4 doesn't have BaseBrowser.
  
  class WindowsHttpDefault(webbrowser.BaseBrowser):
    """Provide an alternate open class for Windows user, using the http handler."""

    def open(self, url, new=0, autoraise=1):
      command_args = create_win32_http_cmd(url)
      if not command_args:
        output('$ Could not find HTTP handler')
        return False

      output('command_args:')
      output(command_args)
      # Avoid some unicode path issues by moving our current directory
      old_pwd = os.getcwd()
      os.chdir('C:\\')
      try:
        _unused = subprocess.Popen(command_args)
        os.chdir(old_pwd)
        return True
      except:
        traceback.print_exc()
        output('$ Failed to run HTTP handler, trying next browser.')
        os.chdir(old_pwd)
        return False

  webbrowser.register('windows-http', WindowsHttpDefault, update_tryorder=-1)
