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
import threading
from Tkinter import *

import base_ui
import history_parser
import util


class WorkerThread(threading.Thread, base_ui.BaseUI):
  """Handle benchmarking and preparation in a separate UI thread."""

  def __init__(self, primary, secondary, options, status_callback=None,
               runstate_callback=None, history_parser=None):
    self.msg('created workerthread')
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
    self.PrepareBenchmark()
    self.RunBenchmark()
    if self.runstate_callback:
      self.runstate_callback(running=False)

class NameBenchGui(Frame, base_ui.BaseUI):
  def __init__(self, options, supplied_ns, global_ns, regional_ns, version=None):
    self.options = options
    self.supplied_ns = supplied_ns
    self.global_ns = global_ns
    self.regional_ns = regional_ns
    self.version = version
    Frame.__init__(self)

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
    self.use_regional = IntVar()

    self.master.title("namebench")
    x_padding = 12

    Label(self.master, text="Nameservers").grid(row=0, columnspan=2, sticky=W, padx=x_padding)

    nameservers = Entry(self.master, bg="white", textvariable=self.nameserver_form, width=70)
    nameservers.grid(row=1, columnspan=2, sticky=W, padx=x_padding+4)
    self.nameserver_form.set(', '.join(util.InternalNameServers()))

    global_button = Checkbutton(self.master, text="Include global DNS providers (OpenDNS, UltraDNS)", variable=self.use_global)
    global_button.grid(row=2, columnspan=2, sticky=W, padx=x_padding)
    global_button.toggle()

    regional_button = Checkbutton(self.master, text="Include best available regional DNS services", variable=self.use_regional)
    regional_button.grid(row=3, columnspan=2, sticky=W, padx=x_padding)
    regional_button.toggle()

    Label(self.master, text="_" * 70).grid(row=4, columnspan=2)

    Label(self.master, text="Benchmark Data Source").grid(row=5, column=0, sticky=W, padx=x_padding)
    Label(self.master, text="Number of tests").grid(row=5, column=1, sticky=W, padx=x_padding)

    self.DiscoverSources()
    source_titles = [history_parser.sourceToTitle(x) for x in self.sources]
    data_source = OptionMenu(self.master, self.data_source, *source_titles)
    data_source.grid(row=6, column=0, sticky=W, padx=x_padding)
    self.data_source.set('Alexa Top 10000')

    num_tests = Entry(self.master, bg="white", textvariable=self.num_tests)
    num_tests.grid(row=6, column=1, sticky=W, padx=x_padding+4)
    self.num_tests.set(self.options.test_count)

    Label(self.master, text="Benchmark Data Selection").grid(row=7, column=0, sticky=W, padx=x_padding)
    Label(self.master, text="Number of runs").grid(row=7, column=1, sticky=W, padx=x_padding)

    selection_mode = OptionMenu(self.master, self.selection_mode, "Weighted", "Random", "Chunk")
    selection_mode.grid(row=8, column=0, sticky=W, padx=x_padding)
    self.selection_mode.set('Weighted')

    num_runs = Entry(self.master, bg="white", textvariable=self.num_runs)
    num_runs.grid(row=8, column=1, sticky=W, padx=x_padding+4)
    self.num_runs.set(self.options.run_count)

    self.button = Button(self.master, command=self.StartJob)
    status = Label(self.master, textvariable=self.status)
    status.grid(row=15, sticky=W, padx=x_padding, pady=8, column=0)
    self.button.grid(row=15, sticky=E, column=1, padx=x_padding, pady=8)
    self.UpdateRunState(running=True)
    self.UpdateRunState(running=False)


  def UpdateStatus(self, message, count=None, total=None, error=None):
    """Update our little status window."""

    # TODO(tstromberg): Add specific Error support
    if total and count:
      state = '%s [%s/%s]' % (message, count, total)
    elif count:
      state = '%s%s' % (message, '.' * count)
    else:
      state = message

    print state
    self.status.set(state)

  def UpdateRunState(self, running=True):
    print '* UpdateRunState: %s' % running

    if running:
      self.button.config(state=DISABLED)
      self.button.config(text='Running')
      self.UpdateStatus('Running...')
    else:
      self.button.config(state=NORMAL)
      self.button.config(text='Start Benchmark')
      self.UpdateStatus('Ready!')

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
