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

import datetime
import os
import Queue
import sys
import threading
import tkFont
# Wildcard imports are evil.
from Tkinter import *
import tkMessageBox
import traceback

import addr_util
import base_ui
import conn_quality
import nameserver_list
import sys_nameservers
import util

THREAD_UNSAFE_TK = 0
LOG_FILE_PATH = util.GenerateOutputFilename('log')


def closedWindowHandler():
  print 'Au revoir, mes amis!'
  sys.exit(1)

global_message_queue = Queue.Queue()
global_last_message = None


def AddMsg(message, master=None, backup_notifier=None, **kwargs):
  """Add a message to the global queue for output."""
  global global_message_queue
  global global_last_message
  global THREAD_UNSAFE_TK

  new_message = StatusMessage(message, **kwargs)
  if new_message != global_last_message:
    global_message_queue.put(new_message)

    if master:
      try:
        master.event_generate('<<msg>>', when='tail')
        global_last_message = new_message
      # Tk thread-safety workaround #1
      except TclError:
        # If we aren't thread safe, we already assume this won't work.
        if not THREAD_UNSAFE_TK:
          print 'First TCL Error:'
          traceback.print_exc()
        try:
          backup_notifier(-1)
          THREAD_UNSAFE_TK = 1
        except:
          print 'Backup notifier failure:'
          traceback.print_exc()


class StatusMessage(object):
  """Messages to be passed from to the main thread from children.

  Used to avoid thread issues inherent with Tk.
  """

  def __init__(self, message, error=False, count=False, total=False,
               enable_button=None, debug=False):
    self.message = message
    self.error = error
    self.count = count
    self.debug = debug
    self.total = total
    self.enable_button = enable_button


class WorkerThread(threading.Thread, base_ui.BaseUI):
  """Handle benchmarking and preparation in a separate UI thread."""

  def __init__(self, supplied_ns, global_ns, regional_ns, options, data_source=None, master=None,
               backup_notifier=None):
    threading.Thread.__init__(self)
    self.SetupDataStructures()
    self.status_callback = self.msg
    self.data_src = data_source
    self.backup_notifier = backup_notifier
    self.include_internal = False
    self.supplied_ns = supplied_ns
    self.global_ns = global_ns
    self.regional_ns = regional_ns
    self.master = master
    self.options = options
    self.resource_dir = os.path.dirname(os.path.dirname(__file__))

  def msg(self, message, **kwargs):
    """Add messages to the main queue."""
    return AddMsg(message, master=self.master, backup_notifier=self.backup_notifier, **kwargs)

  def run(self):
    self.msg('Started thread', enable_button=False)
    try:
      self.PrepareTestRecords()
      self.PrepareNameServers()
      self.PrepareBenchmark()
      self.RunAndOpenReports()
    except nameserver_list.OutgoingUdpInterception:
      (exc_type, exception, tb) = sys.exc_info()
      self.msg('Outgoing requests were intercepted!', error=exception)
    except nameserver_list.TooFewNameservers:
      (exc_type, exception, tb) = sys.exc_info()
      self.msg('Too few nameservers to test', error=exception)
    except conn_quality.OfflineConnection:
      (exc_type, exception, tb) = sys.exc_info()
      self.msg('The connection appears to be offline!', error=exception)
    except:
      (exc_type, exception, tb) = sys.exc_info()
      traceback.print_exc(tb)
      error_msg = '\n'.join(traceback.format_tb(tb)[-4:])
      self.msg(exception, error=error_msg)
    self.msg(None, enable_button=True)


class NameBenchGui(object):
  """The main GUI."""

  def __init__(self, options, supplied_ns, global_ns, regional_ns, version=None):
    self.options = options
    self.supplied_ns = supplied_ns
    self.global_ns = global_ns
    self.regional_ns = regional_ns
    self.version = version

  def Execute(self):
    self.root = Tk()
    app = MainWindow(self.root, self.options, self.supplied_ns, self.global_ns,
                     self.regional_ns, self.version)
    app.DrawWindow()
    self.root.bind('<<msg>>', app.MessageHandler)
    self.root.mainloop()


class MainWindow(Frame, base_ui.BaseUI):
  """The main Tk GUI class."""

  def __init__(self, master, options, supplied_ns, global_ns, regional_ns, version=None):
    """TODO(tstromberg): Remove duplication from NameBenchGui class."""
    Frame.__init__(self)
    self.SetupDataStructures()
    self.master = master
    self.options = options
    self.supplied_ns = supplied_ns
    self.global_ns = global_ns
    self.regional_ns = regional_ns
    self.version = version
    try:
      self.log_file = open(LOG_FILE_PATH, 'w')
    except:
      print 'Failed to open %s for write' % LOG_FILE_PATH
    self.master.protocol('WM_DELETE_WINDOW', closedWindowHandler)

  def UpdateStatus(self, message, count=None, total=None, error=None, debug=False):
    """Update our little status window."""
    if not message:
      return None

    if total:
      state = '%s... [%s/%s]' % (message, count, total)
    elif count:
      state = '%s%s' % (message, '.' * count)
    else:
      state = message

    print '> %s' % str(state)
    try:
      self.log_file.write('%s: %s\r\n' % (datetime.datetime.now(), state))
      self.log_file.flush()
    except:
      pass
    if not debug:
      self.status.set(state[0:75])

  def DrawWindow(self):
    """Draws the user interface."""
    self.nameserver_form = StringVar()
    self.status = StringVar()
    self.query_count = IntVar()
    self.data_source = StringVar()
    self.health_performance = StringVar()
    self.location = StringVar()
    self.use_global = IntVar()
    self.use_regional = IntVar()
    self.use_censor_checks = IntVar()
    self.share_results = IntVar()

    self.master.title('namebench')
    outer_frame = Frame(self.master)
    outer_frame.grid(row=0, padx=16, pady=16)
    inner_frame = Frame(outer_frame, relief=GROOVE, bd=2, padx=12, pady=12)
    inner_frame.grid(row=0, columnspan=2)
    status = Label(outer_frame, text='...', textvariable=self.status)
    status.grid(row=15, sticky=W, column=0)

    if sys.platform[:3] == 'win':
      seperator_width = 490
    else:
      seperator_width = 585

    bold_font = tkFont.Font(font=status['font'])
    bold_font['weight'] = 'bold'

    ns_label = Label(inner_frame, text='Nameservers')
    ns_label.grid(row=0, columnspan=2, sticky=W)
    ns_label['font'] = bold_font

    nameservers = Entry(inner_frame, bg='white',
                        textvariable=self.nameserver_form,
                        width=80)
    nameservers.grid(row=1, columnspan=2, sticky=W, padx=4, pady=2)
    self.nameserver_form.set(', '.join(nameserver_list.InternalNameServers()))

    global_button = Checkbutton(inner_frame,
                                text='Include global DNS providers (Google Public DNS, OpenDNS, UltraDNS, etc.)',
                                variable=self.use_global)
    global_button.grid(row=2, columnspan=2, sticky=W)
    global_button.toggle()

    regional_button = Checkbutton(inner_frame,
                                  text='Include best available regional DNS services',
                                  variable=self.use_regional)
    regional_button.grid(row=3, columnspan=2, sticky=W)
    regional_button.toggle()

    separator = Frame(inner_frame, height=2, width=seperator_width, bd=1, relief=SUNKEN)
    separator.grid(row=4, padx=5, pady=5, columnspan=2)

    ds_label = Label(inner_frame, text='Options')
    ds_label.grid(row=5, column=0, sticky=W)
    ds_label['font'] = bold_font

    censorship_button = Checkbutton(inner_frame, text='Include censorship checks',
                                    variable=self.use_censor_checks)
    censorship_button.grid(row=6, columnspan=2, sticky=W)

    share_button = Checkbutton(inner_frame,
                               text='Upload and share your anonymized results (help speed up the internet!)',
                               variable=self.share_results)

    # Old versions of Tk do not support two-dimensional padding.
    try:
      share_button.grid(row=7, columnspan=2, sticky=W, pady=[0,10])
    except TclError:
      share_button.grid(row=7, columnspan=2, sticky=W)

    loc_label = Label(inner_frame, text='Your location')
    loc_label.grid(row=10, column=0, sticky=W)
    loc_label['font'] = bold_font

    run_count_label = Label(inner_frame, text='Health Check Performance')
    run_count_label.grid(row=10, column=1, sticky=W)
    run_count_label['font'] = bold_font

    self.DiscoverLocation()
    self.LoadDataSources()
    source_titles = self.data_src.ListSourceTitles()
    left_dropdown_width = max([len(x) for x in source_titles]) - 3

    location_choices = [self.country, '(Other)']
    location = OptionMenu(inner_frame, self.location, *location_choices)
    location.configure(width=left_dropdown_width)
    location.grid(row=11, column=0, sticky=W)
    self.location.set(location_choices[0])

    mode_choices = ['Fast', 'Slow (unstable network)']
    right_dropdown_width = max([len(x) for x in mode_choices]) - 3
    health_performance = OptionMenu(inner_frame, self.health_performance, *mode_choices)
    health_performance.configure(width=right_dropdown_width)
    health_performance.grid(row=11, column=1, sticky=W)
    self.health_performance.set(mode_choices[0])

    ds_label = Label(inner_frame, text='Query Data Source')
    ds_label.grid(row=12, column=0, sticky=W)
    ds_label['font'] = bold_font

    numqueries_label = Label(inner_frame, text='Number of queries')
    numqueries_label.grid(row=12, column=1, sticky=W)
    numqueries_label['font'] = bold_font

    data_source = OptionMenu(inner_frame, self.data_source, *source_titles)
    data_source.configure(width=left_dropdown_width)
    data_source.grid(row=13, column=0, sticky=W)
    self.data_source.set(source_titles[0])

    query_count = Entry(inner_frame, bg='white', textvariable=self.query_count)
    query_count.grid(row=13, column=1, sticky=W, padx=4)
    query_count.configure(width=right_dropdown_width + 6)
    self.query_count.set(self.options.query_count)

    self.button = Button(outer_frame, command=self.StartJob)
    self.button.grid(row=15, sticky=E, column=1, pady=4, padx=1)
    self.UpdateRunState(running=True)
    self.UpdateRunState(running=False)
    self.UpdateStatus('namebench %s is ready!' % self.version)

  def MessageHandler(self, unused_event):
    """Pinged when there is a new message in our queue to handle."""
    while global_message_queue.qsize():
      m = global_message_queue.get()
      if m.error:
        self.ErrorPopup(m.message, m.error)
      elif m.enable_button == False:
        self.UpdateRunState(running=True)
      elif m.enable_button == True:
        self.UpdateRunState(running=False)
      self.UpdateStatus(m.message, count=m.count, total=m.total, error=m.error, debug=m.debug)

  def ErrorPopup(self, title, message):
    print 'Showing popup: %s' % title
    tkMessageBox.showerror(str(title), str(message), master=self.master)

  def UpdateRunState(self, running=True):
    """Update the run state of the window, using nasty threading hacks."""

    global THREAD_UNSAFE_TK
    # try/except blocks added to work around broken Tcl/Tk libraries
    # shipped with Fedora 11 (not thread-safe).
    # See http://code.google.com/p/namebench/issues/detail?id=23'
    if THREAD_UNSAFE_TK:
      return

    if running:
      try:
        self.button.config(state=DISABLED)
        self.button.config(text='Running')
      except TclError:
        THREAD_UNSAFE_TK = True
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
    thread = WorkerThread(self.supplied_ns, self.global_ns, self.regional_ns, self.options,
                          data_source=self.data_src,
                          master=self.master, backup_notifier=self.MessageHandler)
    thread.start()

  def ProcessForm(self):
    """Read form and populate instance variables."""

    self.supplied_ns = addr_util.ExtractIPTuplesFromString(self.nameserver_form.get())
    if not self.use_global.get():
      self.global_ns = []
    if not self.use_regional.get():
      self.regional_ns = []

    if 'Slow' in self.health_performance.get():
      self.options.health_thread_count = 10

    self.options.query_count = self.query_count.get()
    self.options.input_source = self.data_src.ConvertSourceTitleToType(self.data_source.get())
    self.options.enable_censorship_checks = self.use_censor_checks.get()
    self.options.upload_results = self.share_results.get()
