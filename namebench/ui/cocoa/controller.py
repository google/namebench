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


import os
import sys
import traceback
from Foundation import *
from AppKit import *
from objc import IBAction, IBOutlet

from libnamebench import addr_util
from libnamebench import base_ui
from libnamebench import config
from libnamebench import conn_quality
from libnamebench import nameserver_list
from libnamebench import util
from libnamebench import version

# How much room do we have in the UI for status messages?
MAX_STATUS_LENGTH = 68


class controller(NSWindowController, base_ui.BaseUI):
  """Controller class associated with the main window."""
  nameserver_form = IBOutlet()
  include_global = IBOutlet()
  include_regional = IBOutlet()
  include_censorship_checks = IBOutlet()
  data_source = IBOutlet()
  health_performance = IBOutlet()
  enable_sharing = IBOutlet()
  location = IBOutlet()
  query_count = IBOutlet()
  run_count = IBOutlet()
  status = IBOutlet()
  spinner = IBOutlet()
  button = IBOutlet()

  def awakeFromNib(self):
    """Initializes our class, called automatically by Cocoa."""
    self.SetupDataStructures()
    self.resource_dir = os.path.join(os.getcwd(), 'namebench.app', 'Contents', 'Resources')

    conf_file = util.FindDataFile('config/namebench.cfg')
    (self.options, self.supplied_ns, self.global_ns, self.regional_ns) = config.GetConfiguration(filename=conf_file)
    # TODO(tstromberg): Consider moving this into a thread for faster loading.
    self.UpdateStatus('Discovering sources')
    self.LoadDataSources()
    self.UpdateStatus('Discovering location')
    self.DiscoverLocation()
    self.UpdateStatus('Populating Form...')
    self.setFormDefaults()
    self.UpdateStatus('namebench %s is ready!' % version.VERSION)

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

    state = state.replace('%', '%%')
    print state
    NSLog(state)
    
    self.status.setStringValue_(state[0:MAX_STATUS_LENGTH])

  def ProcessForm(self):
    """Parse the form fields and populate class variables."""
    self.UpdateStatus('Processing form inputs')
    self.preferred = self.supplied_ns
    self.include_internal = False

    if not int(self.include_global.stringValue()):
      self.UpdateStatus('Not using global')
      self.global_ns = []
    else:
      self.preferred.extend(self.global_ns)
    if not int(self.include_regional.stringValue()):
      self.UpdateStatus('Not using regional')
      self.regional_ns = []

    if int(self.enable_sharing.stringValue()):
      self.options.upload_results = True

    if int(self.include_censorship_checks.stringValue()):
      self.options.enable_censorship_checks = True

    print self.health_performance.titleOfSelectedItem()
    if 'Slow' in self.health_performance.titleOfSelectedItem():
      self.options.health_thread_count = 10

    self.options.input_source = self.data_src.ConvertSourceTitleToType(self.data_source.titleOfSelectedItem())
    self.UpdateStatus('Supplied servers: %s' % self.nameserver_form.stringValue())
    self.preferred.extend(addr_util.ExtractIPTuplesFromString(self.nameserver_form.stringValue()))
    self.options.query_count = int(self.query_count.stringValue())

  def benchmarkThread(self):
    """Run the benchmarks, designed to be run in a thread."""
    pool = NSAutoreleasePool.alloc().init()
    self.spinner.startAnimation_(self)
    self.button.setEnabled_(False)
    self.UpdateStatus('Preparing benchmark')
    try:
      self.PrepareTestRecords()
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
    except conn_quality.OfflineConnection:
      (exc_type, exception, tb) = sys.exc_info()
      self.UpdateStatus('The connection appears to be offline!', error=str(exception))
    except:
      (exc_type, exception, tb) = sys.exc_info()
      traceback.print_exc(tb)
      error_msg = '\n'.join(traceback.format_tb(tb)[-4:])
      self.UpdateStatus('FAIL: %s' % exception, error=error_msg)

    self.spinner.stopAnimation_(self)
    self.button.setEnabled_(True)
    # This seems weird, but recommended by http://pyobjc.sourceforge.net/documentation/pyobjc-core/intro.html
    del pool

  def displayError(self, msg, details):
    """Display an alert drop-down message."""
    NSLog('ERROR: %s - %s' % (msg, details))
    alert = NSAlert.alloc().init()
    alert.setMessageText_(msg)
    alert.setInformativeText_(details)
    buttonPressed = alert.runModal()

  def setFormDefaults(self):
    """Set up the form with sane initial values."""
    nameservers_string = ', '.join(nameserver_list.InternalNameServers())
    self.nameserver_form.setStringValue_(nameservers_string)
    self.query_count.setStringValue_(self.options.query_count)
    self.query_count.setStringValue_(self.options.query_count)

    self.location.removeAllItems()
    if self.country:
      self.location.addItemWithTitle_(self.country)
      self.location.addItemWithTitle_('(Other)')
    else:
      self.location.addItemWithTitle_('(automatic)')

    self.health_performance.removeAllItems()
    self.health_performance.addItemWithTitle_('Fast')
    self.health_performance.addItemWithTitle_('Slow (unstable network)')

    self.data_source.removeAllItems()
    self.data_source.addItemsWithTitles_(self.data_src.ListSourceTitles())

