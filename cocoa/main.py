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

"""Cocoa frontend loader for namebench."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import platform
print "Starting up on Python %s [%s] compiled with %s" % (platform.python_version(),
                                                          platform.platform(),
                                                          platform.python_compiler())

#import modules required by application
import objc
import Foundation
import AppKit

from PyObjCTools import AppHelper

# import modules containing classes required to start application and load MainMenu.nib
import namebenchAppDelegate
import controller

# pass control to AppKit
AppHelper.runEventLoop()

