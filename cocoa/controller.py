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


"""Cocoa frontend implementation for namebench."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'


from objc import YES, NO, IBAction, IBOutlet
from Foundation import *
from AppKit import *
import datetime
import operator
import urllib
import time
import webbrowser
import tempfile
import sys
import os
import re

# TODO(tstromberg): Research best practices for bundling cocoa frontends.
pwd = os.getcwd()
if 'namebench/cocoa/' in pwd:
  NSLog("Enabling development mode resource hack")
  RSRC_DIR = pwd[0:pwd.index('/cocoa/')]
  sys.path.append(RSRC_DIR)
else:
  RSRC_DIR = os.path.dirname(__file__)

NSLog("Resource directory is %s" % RSRC_DIR)
from lib import config
from lib import nameserver_list
from lib import third_party
from lib import benchmark
from lib import util
from lib import history_parser

class controller(NSWindowController):
  """Controller class associated with the main window."""
  nameserver_form = IBOutlet()
  include_global = IBOutlet()
  include_regional = IBOutlet()
  data_source = IBOutlet()
  selection_mode = IBOutlet()
  num_tests = IBOutlet()
  num_runs = IBOutlet()

  status = IBOutlet()
  spinner = IBOutlet()

  def awakeFromNib(self):
    """Initializes our class, called automatically by Cocoa"""

    conf_file = os.path.join(RSRC_DIR, 'namebench.cfg')
    NSLog("Using configuration: %s" % conf_file)
    (self.options, self.supplied_ns, self.global_ns, self.regional_ns) = config.GetConfiguration(filename=conf_file)
    # TODO(tstromberg): Consider moving this into a thread for faster loading.
    self.imported_records = None
    self.updateStatus('Discovering sources')
    self.discoverSources()
    self.updateStatus('Populating Form...')
    self.setFormDefaults()
    self.updateStatus('Ready')

  @IBAction
  def startJob_(self, sender):
    """Trigger for the 'Start Benchmark' button, starts benchmark thread."""
    self.ProcessForm()
    self.updateStatus('Starting benchmark thread')
    t = NSThread.alloc().initWithTarget_selector_object_(self, self.benchmarkThread, None)
    t.start()

  def updateStatus(self, message, count=None, total=None, error=False):
    """Update the status message at the bottom of the window."""
    if error:
      return self.displayError("Error", message)
    if total and count:
      state = '%s [%s/%s]' % (message, count, total)
    elif count:
      state = '%s%s' % (message, '.' * count)
    else:
      state = message

    NSLog(state)
    self.status.setStringValue_(state)

  def ProcessForm(self):
    """Parse the form fields and populate class variables."""
    self.updateStatus('Processing form inputs')
    self.primary = self.supplied_nss

    if not int(self.include_global.stringValue()):
      self.updateStatus('Not using primary')
    else:
      self.primary.extend(self.global_ns)
    if not int(self.include_regional.stringValue()):
      self.updateStatus('Not using secondary')
      self.secondary = []
    else:
      self.secondary = self.regional_ns

    self.select_mode = self.selection_mode.titleOfSelectedItem().lower()
    self.imported_records = self.GetSourceData(self.data_source.titleOfSelectedItem())
    self.updateStatus('Supplied servers: %s' % self.nameserver_form.stringValue())
    self.primary.extend(util.ExtractIPTuplesFromString(self.nameserver_form.stringValue()))
    self.options.test_count = int(self.num_tests.stringValue())
    self.options.run_count = int(self.num_runs.stringValue())
    self.updateStatus("%s tests, %s runs" % (self.options.test_count, self.options.run_count))

  def benchmarkThread(self):
    """Run the benchmarks, designed to be run in a thread."""
    pool = NSAutoreleasePool.alloc().init()
    self.spinner.startAnimation_(self)
    self.updateStatus('Preparing benchmark')
    self.PrepareBenchmark(self)
    self.RunBenchmark(self)
    self.spinner.stopAnimation_(self)
    pool.release()



  def displayError(self, msg, details):
    """Display an alert drop-down message"""
    NSLog("ERROR: %s - %s" % (msg, details))
    alert = NSAlert.alloc().init()
    alert.setMessageText_(msg)
    alert.setInformativeText_(details)
    buttonPressed = alert.runModal()


  def setFormDefaults(self):
    """Set up the form with sane initial values."""
    nameservers_string = ', '.join(util.InternalNameServers())
    self.nameserver_form.setStringValue_(nameservers_string)
    self.num_tests.setStringValue_(self.options.test_count)
    self.num_runs.setStringValue_(self.options.run_count)
    self.selection_mode.removeAllItems()
    self.selection_mode.addItemsWithTitles_(['Weighted', 'Random', 'Chunk'])
    self.data_source.removeAllItems()
    for source in self.sources:
      self.data_source.addItemWithTitle_(history_parser.sourceToTitle(source))

