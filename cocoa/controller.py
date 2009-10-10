#
#  controller.py
#  namebench
#
#  Created by Thomas Stromberg on 9/10/09.
#  Copyright (c) 2009 __MyCompanyName__. All rights reserved.
#

from objc import YES, NO, IBAction, IBOutlet
from Foundation import *
from AppKit import *
import time
import webbrowser
import sys

# TODO(tstromberg): Research best practices for bundling cocoa frontends.
NB_SOURCE = '/Volumes/snabbt/Users/tstromberg/namebench'
sys.path.append(NB_SOURCE)
from lib import nameserver_list
from lib import third_party
from lib import benchmark

class controller(NSWindowController):
	form_data = IBOutlet()
	status = IBOutlet()
	spinner = IBOutlet()
	
	def updateStatus(self, message):
		NSLog(message)
		self.status.setStringValue_(message)

	@IBAction
	def startJob_(self, sender):
		self.updateStatus('Starting benchmark thread')
		t = NSThread.alloc().initWithTarget_selector_object_(self, self.benchmarkThread, None)
		t.start()
				
	def benchmarkThread(self):
		pool = NSAutoreleasePool.alloc().init()
		self.spinner.startAnimation_(self)		
		primary = self.form_data.stringValue()
		self.updateStatus('Using %s' % primary)
		nameservers = nameserver_list.NameServers([(primary,primary)])
		self.updateStatus('Preparing benchmark')
		bmark = benchmark.Benchmark(nameservers, test_count=110, run_count=1)
		bmark.CreateTestsFromFile('%s/data/alexa-top-10000-global.txt' % NB_SOURCE)
		self.updateStatus('Running...')
		bmark.Run()
		self.updateStatus('Displaying Results...')
		bmark.DisplayResults()
		self.updateStatus('Saving results')
		bmark.SaveResultsToCsv('output.csv')
		self.spinner.stopAnimation_(self)		
		best = bmark.BestOverallNameServer()
		self.updateStatus('%s looks like the winner' % best.ip)
		pool.release()
		
	def awakeFromNib(self):
		self.updateStatus('Ready')
