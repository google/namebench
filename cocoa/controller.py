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
import traceback
import sys
import os
import re

import third_party
from libnamebench import base_ui
from libnamebench import config
from libnamebench import nameserver_list
from libnamebench import benchmark
from libnamebench import util
from libnamebench import history_parser

class controller(NSWindowController, base_ui.BaseUI):
  """Controller class associated with the main window."""
  nameserver_form = IBOutlet()
  include_global = IBOutlet()
  include_regional = IBOutlet()
  include_censorship_checks = IBOutlet()
  data_source = IBOutlet()
  selection_mode = IBOutlet()
  num_tests = IBOutlet()
  num_runs = IBOutlet()
  status = IBOutlet()
  spinner = IBOutlet()
  button = IBOutlet()

  def awakeFromNib(self):
    """Initializes our class, called automatically by Cocoa"""

    self.resource_dir = os.path.join(os.getcwd(), 'namebench.app', 'Contents', 'Resources')
    conf_file = os.path.join(self.resource_dir, 'namebench.cfg')
    NSLog("Using configuration: %s" % conf_file)
    (self.options, self.supplied_ns, self.global_ns, self.regional_ns) = config.GetConfiguration(filename=conf_file)
    # TODO(tstromberg): Consider moving this into a thread for faster loading.
    self.UpdateStatus('Discovering sources')
    self.DiscoverSources()
    self.UpdateStatus('Populating Form...')
    self.setFormDefaults()
    self.UpdateStatus('Ready')

  @IBAction
  def startJob_(self, sender):
    """Trigger for the 'Start Benchmark' button, starts benchmark thread."""
    self.ProcessForm()
    self.UpdateStatus('Starting benchmark thread')
    t = NSThread.alloc().initWithTarget_selector_object_(self, self.benchmarkThread, None)
    t.start()

  def UpdateStatus(self, message, count=None, total=None, error=False, debug=False):
    """Update the status message at the bottom of the window."""
    if error:
      return self.displayError(message, error)
    if total:
      state = '%s [%s/%s]' % (message, count, total)
    elif count:
      state = '%s%s' % (message, '.' * count)
    else:
      state = message

    NSLog(state)
    self.status.setStringValue_(state)

  def ProcessForm(self):
    """Parse the form fields and populate class variables."""
    self.UpdateStatus('Processing form inputs')
    self.preferred = self.supplied_ns
    self.include_internal = False
    
    if not int(self.include_global.stringValue()):
      self.UpdateStatus('Not using primary')
    else:
      self.preferred.extend(self.global_ns)
    if not int(self.include_regional.stringValue()):
      self.UpdateStatus('Not using secondary')
      self.secondary = []
    else:
      self.secondary = self.regional_ns

    if int(self.include_censorship_checks.stringValue()):
      self.options.enable_censorship_checks = True
    self.options.select_mode = self.selection_mode.titleOfSelectedItem().lower()
    self.options.data_source = self.ParseSourceSelection(self.data_source.titleOfSelectedItem())
    self.UpdateStatus('Supplied servers: %s' % self.nameserver_form.stringValue())
    self.preferred.extend(util.ExtractIPTuplesFromString(self.nameserver_form.stringValue()))
    self.options.test_count = int(self.num_tests.stringValue())
    self.options.run_count = int(self.num_runs.stringValue())
    self.UpdateStatus("Source %s, mode %s, %s tests, %s runs" % (self.options.data_source, self.options.select_mode, self.options.test_count, self.options.run_count))

  def benchmarkThread(self):
    """Run the benchmarks, designed to be run in a thread."""
    pool = NSAutoreleasePool.alloc().init()
    self.spinner.startAnimation_(self)
    self.button.setEnabled_(False)
    self.UpdateStatus('Preparing benchmark')
    try:
      self.PrepareNameServers()
      self.PrepareBenchmark()
      self.RunAndOpenReports()
    except nameserver_list.OutgoingUdpInterception:
      (exc_type, exception, tb) = sys.exc_info()
      self.UpdateStatus('Outgoing requests were intercepted!',
                        error=str(exception))
    except nameserver_list.TooFewNameservers:
      (exc_type, exception, tb) = sys.exc_info()
      self.UpdateStatus('Too few nameservers to test', error=str(exception))
    except:
      (exc_type, exception, tb) = sys.exc_info()
      traceback.print_exc(tb)
      error_msg = '\n'.join(traceback.format_tb(tb)[-4:])
      self.UpdateStatus('FAIL: %s' % exception, error=error_msg)

    self.spinner.stopAnimation_(self)
    self.button.setEnabled_(True)
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

