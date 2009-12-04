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

"""Tk user interface implementation for namebench."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import os
import sys
import threading
import tkFont
import traceback
from Tkinter import *
import tkMessageBox

import base_ui
import history_parser
import nameserver_list
import util

def closedWindowHandler():
  print 'Au revoir, mes amis!'
  sys.exit(1)

class WorkerThread(threading.Thread, base_ui.BaseUI):
  """Handle benchmarking and preparation in a separate UI thread."""

  def __init__(self, primary, secondary, options, status_callback=None,
               runstate_callback=None, history_parser=None):
    self.UpdateStatus('created workerthread')
    threading.Thread.__init__(self)
    self.runstate_callback = runstate_callback
    self.status_callback = status_callback
    self.hparser = history_parser
    self.primary = primary
    self.secondary = secondary
    self.options = options
    self.resource_dir = os.path.dirname(os.path.dirname(__file__))

  def run(self):
    if self.runstate_callback:
      self.runstate_callback(running=True)
    try:
      self.PrepareBenchmark()
      self.UpdateStatus('Here comes the pain...')
      self.RunBenchmark()
    except nameserver_list.OutgoingUdpInterception:
      (exc_type, exception, tb) = sys.exc_info()
      self.UpdateStatus('Outgoing requests were intercepted!',
                        error=exception)
    except nameserver_list.TooFewNameservers:
      (exc_type, exception, tb) = sys.exc_info()
      self.UpdateStatus('Too few nameservers to test', error=exception)
    except:
      (exc_type, exception, tb) = sys.exc_info()
      print "-- FAIL ----------------------------------------------------------"
      traceback.print_exc(tb)
      print "------------------------------------------------------------------"
      error_msg = '\n'.join(traceback.format_tb(tb)[-4:])
      self.UpdateStatus('FAIL: %s' % exception, error=error_msg)
    if self.runstate_callback:
      self.runstate_callback(running=False)


class NameBenchGui(Frame, base_ui.BaseUI):
  """The main Tk GUI class."""

  def __init__(self, options, supplied_ns, global_ns, regional_ns, version=None):
    self.options = options
    self.supplied_ns = supplied_ns
    self.global_ns = global_ns
    self.regional_ns = regional_ns
    self.version = version
    Frame.__init__(self)
    self.master.protocol('WM_DELETE_WINDOW', closedWindowHandler)

  def Execute(self):
    """Called by namebench.py, begins the UI drawing process."""
    self.DrawWindow()
    self.mainloop()

  def DrawWindow(self):
    """Draws the user interface."""
    self.nameserver_form = StringVar()
    self.status = StringVar()
    self.num_tests = IntVar()
    self.num_runs = IntVar()
    self.data_source = StringVar()
    self.selection_mode = StringVar()
    self.use_global = IntVar()
    self.broken_tk = False
    self.use_regional = IntVar()

    self.master.title("namebench")
    outer_frame = Frame(self.master)
    outer_frame.grid(row=0, padx=16, pady=16)
    inner_frame = Frame(outer_frame, relief=GROOVE, bd=2, padx=12, pady=12)
    inner_frame.grid(row=0, columnspan=2)
    status = Label(outer_frame, text='...', textvariable=self.status)
    status.grid(row=15, sticky=W, column=0)

    bold_font = tkFont.Font(font=status['font'])
    bold_font['weight'] = 'bold'

    ns_label = Label(inner_frame, text="Nameservers")
    ns_label.grid(row=0, columnspan=2, sticky=W)
    ns_label['font'] = bold_font

    nameservers = Entry(inner_frame, bg="white", textvariable=self.nameserver_form, width=65)
    nameservers.grid(row=1, columnspan=2, sticky=W, padx=4, pady=2)
    self.nameserver_form.set(', '.join(util.InternalNameServers()))

    global_button = Checkbutton(inner_frame, text="Include global DNS providers (OpenDNS, UltraDNS)", variable=self.use_global)
    global_button.grid(row=2, columnspan=2, sticky=W)
    global_button.toggle()

    regional_button = Checkbutton(inner_frame, text="Include best available regional DNS services", variable=self.use_regional)
    regional_button.grid(row=3, columnspan=2, sticky=W)
    regional_button.toggle()

    separator = Frame(inner_frame, height=2, width=515, bd=1, relief=SUNKEN)
    separator.grid(row=4, padx=5, pady=5, columnspan=2)

    ds_label = Label(inner_frame, text="Benchmark Data Source")
    ds_label.grid(row=5, column=0, sticky=W)
    ds_label['font'] = bold_font

    numtests_label = Label(inner_frame, text="Number of tests")
    numtests_label.grid(row=5, column=1, sticky=W)
    numtests_label['font'] = bold_font

    self.DiscoverSources()
    source_titles = [history_parser.sourceToTitle(x) for x in self.sources]
    data_source = OptionMenu(inner_frame, self.data_source, *source_titles)
    data_source.configure(width=35)
    data_source.grid(row=6, column=0, sticky=W)
    self.data_source.set(source_titles[0])

    num_tests = Entry(inner_frame, bg="white", textvariable=self.num_tests)
    num_tests.grid(row=6, column=1, sticky=W, padx=4)
    self.num_tests.set(self.options.test_count)

    bds_label = Label(inner_frame, text="Benchmark Data Selection")
    bds_label.grid(row=7, column=0, sticky=W)
    bds_label['font'] = bold_font

    num_runs_label = Label(inner_frame, text="Number of runs")
    num_runs_label.grid(row=7, column=1, sticky=W)
    num_runs_label['font'] = bold_font

    selection_mode = OptionMenu(inner_frame, self.selection_mode, "Weighted", "Random", "Chunk")
    selection_mode.configure(width=35)
    selection_mode.grid(row=8, column=0, sticky=W)
    self.selection_mode.set('Weighted')

    num_runs = Entry(inner_frame, bg="white", textvariable=self.num_runs)
    num_runs.grid(row=8, column=1, sticky=W, padx=4)
    self.num_runs.set(self.options.run_count)

    self.button = Button(outer_frame, command=self.StartJob)
    self.button.grid(row=15, sticky=E, column=1, pady=4, padx=1)
    self.UpdateRunState(running=True)
    self.UpdateRunState(running=False)
    self.UpdateStatus('Ready')


  def UpdateStatus(self, message, count=None, total=None, error=None):
    """Update our little status window."""

    # TODO(tstromberg): Add specific Error support
    if total:
      state = '%s... [%s/%s]' % (message, count, total)
    elif count:
      state = '%s%s' % (message, '.' * count)
    else:
      state = message

    if error:
      print "> %s [%s]" % (state, error)
      tkMessageBox.showerror(message, error)
    else:
      print "> %s" % state
    self.status.set(state[0:60])

  def UpdateRunState(self, running=True):
    # try/except blocks added to work around broken Tcl/Tk libraries
    # shipped with Fedora 11 (not thread-safe).
    # See http://code.google.com/p/namebench/issues/detail?id=23'
    if self.broken_tk:
      return

    if running:
      try:
        self.button.config(state=DISABLED)
        self.button.config(text='Running')
      except TclError:
        self.broken_tk = True
        self.UpdateStatus('Unable to disable button due to broken Tk library')
      self.UpdateStatus('Running...')
    else:
      try:
        self.button.config(state=NORMAL)
        self.button.config(text='Start Benchmark')
      except TclError:
        pass

  def StartJob(self):
    """Events that get called when the Start button is pressed."""

    self.ProcessForm()
    thread = WorkerThread(self.primary, self.secondary, self.options,
                          history_parser=self.hparser,
                          status_callback=self.UpdateStatus,
                          runstate_callback=self.UpdateRunState)
    thread.start()

  def ProcessForm(self):
    """Read form and populate instance variables."""
    self.primary = self.supplied_ns + util.ExtractIPTuplesFromString(self.nameserver_form.get())
    print 'GLOBAL: %s' % self.use_global.get()

    if self.use_global.get():
      self.primary += self.global_ns
    if self.use_regional.get():
      self.secondary = self.regional_ns
    else:
      self.secondary = []
    self.options.run_count = self.num_runs.get()
    self.options.test_count = self.num_tests.get()
    self.options.data_source = self.ParseSourceSelection(self.data_source.get())
    self.options.select_mode = self.selection_mode.get().lower()
