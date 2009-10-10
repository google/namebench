#
#  namebenchAppDelegate.py
#  namebench
#
#  Created by Thomas Stromberg on 9/10/09.
#  Copyright __MyCompanyName__ 2009. All rights reserved.
#

from Foundation import *
from AppKit import *

class namebenchAppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, sender):
        NSLog("Application did finish launching.")
