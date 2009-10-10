#
#  main.py
#  namebench
#
#  Created by Thomas Stromberg on 9/10/09.
#  Copyright __MyCompanyName__ 2009. All rights reserved.
#

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

