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
import Queue
from Tkinter import *
import tkMessageBox

from . import base_ui
from . import conn_quality
from . import data_sources
from . import nameserver_list
from . import selectors
from . import util

THREAD_UNSAFE_TK = 0

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

  new_message = Message(message, **kwargs)
  if new_message != global_last_message:
    global_message_queue.put(new_message)

    if master:
      try:
        master.event_generate('<<msg>>', when='tail')
        global_last_message = new_message
      # Tk thread-safety workaround #1
      except TclError:
        try:
          backup_notifier(-1)
          THREAD_UNSAFE_TK = 1
        except:
          print "TCL error encountered, not pushing update to UI:"
          traceback.print_exc()

class Message(object):
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

  def __init__(self, preferred, secondary, options, data_source=None, master=None,
               backup_notifier=None):
    threading.Thread.__init__(self)
    self.status_callback = self.msg
    self.data_src = data_source
    self.backup_notifier = backup_notifier
    self.include_internal = False
    self.preferred = preferred
    self.master = master
    self.secondary = secondary
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
    app = MainWindow(self.root, self.options, self.supplied_ns, self.global_ns, self.regional_ns, self.version)
    app.DrawWindow()
    self.root.bind('<<msg>>', app.MessageHandler)
    self.root.mainloop()


class MainWindow(Frame, base_ui.BaseUI):
  """The main Tk GUI class."""

  def __init__(self, master, options, supplied_ns, global_ns, regional_ns, version=None):
    """TODO(tstromberg): Remove duplication from NameBenchGui class."""
    Frame.__init__(self)
    self.master = master
    self.options = options
    self.supplied_ns = supplied_ns
    self.global_ns = global_ns
    self.regional_ns = regional_ns
    self.version = version
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

    print "> %s" % state
    self.status.set(state[0:75])

  def DrawWindow(self):
    """Draws the user interface."""
    self.nameserver_form = StringVar()
    self.status = StringVar()
    self.query_count = IntVar()
    self.run_count = IntVar()
    self.data_source = StringVar()
    self.selection_mode = StringVar()
    self.use_global = IntVar()
    self.use_regional = IntVar()
    self.use_censor_checks = IntVar()

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

    nameservers = Entry(inner_frame, bg="white", textvariable=self.nameserver_form, width=80)
    nameservers.grid(row=1, columnspan=2, sticky=W, padx=4, pady=2)
    self.nameserver_form.set(', '.join(util.InternalNameServers()))

    global_button = Checkbutton(inner_frame, text="Include global DNS providers (Google Public DNS, OpenDNS, UltraDNS, etc.)", variable=self.use_global)
    global_button.grid(row=2, columnspan=2, sticky=W)
    global_button.toggle()

    regional_button = Checkbutton(inner_frame, text="Include best available regional DNS services", variable=self.use_regional)
    regional_button.grid(row=3, columnspan=2, sticky=W)
    regional_button.toggle()

    censorship_button = Checkbutton(inner_frame, text="Include censorship checks", variable=self.use_censor_checks)
    censorship_button.grid(row=4, columnspan=2, sticky=W)

    if sys.platform[:3] == 'win':
      seperator_width = 470
    else:
      seperator_width = 585
    separator = Frame(inner_frame, height=2, width=seperator_width, bd=1, relief=SUNKEN)
    separator.grid(row=5, padx=5, pady=5, columnspan=2)

    ds_label = Label(inner_frame, text="Test Data Source")
    ds_label.grid(row=10, column=0, sticky=W)
    ds_label['font'] = bold_font

    numqueries_label = Label(inner_frame, text="Number of queries")
    numqueries_label.grid(row=10, column=1, sticky=W)
    numqueries_label['font'] = bold_font

    self.LoadDataSources()
    source_titles = self.data_src.ListSourceTitles()
    data_source = OptionMenu(inner_frame, self.data_source, *source_titles)
    data_source.configure(width=40)
    data_source.grid(row=11, column=0, sticky=W)
    self.data_source.set(source_titles[0])

    query_count = Entry(inner_frame, bg="white", textvariable=self.query_count)
    query_count.grid(row=11, column=1, sticky=W, padx=4)
    self.query_count.set(self.options.query_count)

    bds_label = Label(inner_frame, text="Test Selection Mode")
    bds_label.grid(row=12, column=0, sticky=W)
    bds_label['font'] = bold_font

    run_count_label = Label(inner_frame, text="Number of runs")
    run_count_label.grid(row=12, column=1, sticky=W)
    run_count_label['font'] = bold_font

    modes = [x.title() for x in selectors.GetTypes()]
    selection_mode = OptionMenu(inner_frame, self.selection_mode, *modes)
    selection_mode.configure(width=40)
    selection_mode.grid(row=13, column=0, sticky=W)
    self.selection_mode.set(modes[0])

    run_count = Entry(inner_frame, bg="white", textvariable=self.run_count)
    run_count.grid(row=13, column=1, sticky=W, padx=4)
    self.run_count.set(self.options.run_count)

    self.button = Button(outer_frame, command=self.StartJob)
    self.button.grid(row=15, sticky=E, column=1, pady=4, padx=1)
    self.UpdateRunState(running=True)
    self.UpdateRunState(running=False)
    self.UpdateStatus('namebench %s is ready!' % self.version)

  def MessageHandler(self, event):
    """Pinged when there is a new message in our queue to handle."""
    while global_message_queue.qsize():
      msg = global_message_queue.get()
      if msg.error:
        self.ErrorPopup(msg.message, msg.error)
      elif msg.enable_button == False:
        self.UpdateRunState(running=True)
      elif msg.enable_button == True:
        self.UpdateRunState(running=False)
      self.UpdateStatus(msg.message, count=msg.count, total=msg.total, error=msg.error)

  def ErrorPopup(self, title, message):
    print "Showing popup: %s" % title
    tkMessageBox.showerror(str(title), str(message), master=self.master)

  def UpdateRunState(self, running=True):
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
    thread = WorkerThread(self.preferred, self.secondary, self.options,
                          data_source=self.data_src,
                          master=self.master, backup_notifier=self.MessageHandler)
    thread.start()

  def ProcessForm(self):
    """Read form and populate instance variables."""
    self.preferred = self.supplied_ns + util.ExtractIPTuplesFromString(self.nameserver_form.get())

    if self.use_global.get():
      self.preferred += self.global_ns
    if self.use_regional.get():
      self.secondary = self.regional_ns
    else:
      self.secondary = []
    self.options.run_count = self.run_count.get()
    self.options.query_count = self.query_count.get()
    self.options.input_source = self.data_src.ConvertSourceTitleToType(self.data_source.get())
    self.options.select_mode = self.selection_mode.get().lower()
    self.options.enable_censorship_checks = self.use_censor_checks.get()