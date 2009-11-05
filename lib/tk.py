#!/usr/bin/env python
import threading
import time
import webbrowser
import tempfile
import os.path
import util
from Tkinter import *

import benchmark
import history_parser
import nameserver_list

class BenchmarkThread(threading.Thread):
  """Quickly test the health of many nameservers with multiple threads."""

  def __init__(self, nameservers, tests=None, status_callback=None):
    threading.Thread.__init__(self)
    self.nameservers = []
    self.tests = tests
    self.num_runs
    self.status_callback = status_callback
    for ip in nameservers:
      self.nameservers.append((ip, ip))

  def updateStatus(self, msg, count=None, total=None):
    """Update the little status message on the bottom of the window."""

    if hasattr(self, 'status_callback') and self.status_callback:
      self.status_callback(msg, count=count, total=total)

  def Run(self):

    self.updateStatus('Preparing benchmark')
    nameservers = nameserver_list.NameServers(self.nameservers, include_internal=True,
                                              status_callback=self.status_callback)
    bmark = benchmark.Benchmark(nameservers, test_count=self.tests, run_count=1,
                                status_callback=self.status_callback)
    bmark.CreateTestsFromFile('%s/data/alexa-top-10000-global.txt' % NB_SOURCE)
    bmark.Run()
    best = bmark.BestOverallNameServer()
    self.UpdateStatus('%s looks pretty good' % best)
    self.CreateReport(bmark)
    return bmark

  def CreateReport(self, bmark):
    output_dir = tempfile.gettempdir()
    report_path = os.path.join(output_dir, 'namebench.html')
    csv_path = os.path.join(output_dir, 'namebench.csv')

    report_file = open(report_path, 'w')
    bmark.CreateReport(output_fp=report_file, format='html')
    report_file.close()

    bmark.SaveResultsToCsv('output.csv')
    webbrowser.open(report_path)

class NameBenchGui(Frame):
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

  def DiscoverSources(self):
    """Seek out and create a list of valid data sources."""
    self.UpdateStatus('Searching for usable data sources')
    self.hparser = history_parser.HistoryParser()
    self.sources = self.hparser.GetAvailableHistorySources()

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
    x_padding=12

    Label(self.master, text="Nameservers").grid(row=0, columnspan=2, sticky=W, padx=x_padding)

    nameservers = Entry(self.master, bg="white", textvariable=self.nameserver_form, width=50)
    nameservers.grid(row=1, columnspan=2, sticky=W, padx=x_padding+4)
    self.nameserver_form.set(', '.join(util.InternalNameServers()))

    global_button = Checkbutton(self.master, text="Include global DNS providers (OpenDNS, UltraDNS)", variable=self.use_global)
    global_button.grid(row=2, columnspan=2, sticky=W, padx=x_padding)
    global_button.toggle()

    regional_button = Checkbutton(self.master, text="Include best available regional DNS services", variable=self.use_regional)
    regional_button.grid(row=3, columnspan=2, sticky=W, padx=x_padding)
    regional_button.toggle()

    Label(self.master, text="_" * 50).grid(row=4, columnspan=2)

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

#    Label(self.master, text="_" * 50).grid(row=14, columnspan=2)
    button = Button(self.master, text = "Start Benchmark", command=self.StartJob)
    status = Label(self.master, textvariable=self.status)
    status.grid(row=15, sticky=W, padx=x_padding, pady=8, column=0)
    button.grid(row=15, sticky=E, column=1, padx=x_padding, pady=8)
    self.UpdateStatus('Ready...')

  def UpdateStatus(self, message, count=None, total=None, error=None):
    """Update our little status window."""
    if total and count:
      state = '%s [%s/%s]' % (message, count, total)
    elif count:
      state = '%s%s' % (message, '.' * count)
    else:
      state = message

    print state
    self.status.set(state)

  def StartJob(self):
    """Events that get called when the Start button is pressed."""
    self.ProcessForm()
    self.StartBenchmark()

  def ProcessForm(self):
    """Read form and populate instance variables."""
    self.primary = self.supplied_ns + util.ExtractIPTuplesFromString(self.nameserver_form.get())
    if self.use_global:
      self.primary = self.primary + self.global_ns
    if self.use_regional:
      self.secondary = self.regional_ns
    else:
      self.secondary = []


  def StartBenchmark(self):
    thread = BenchmarkThread(servers, tests=self.tests_num.get(),
                             status_callback=self.UpdateStatus)
    thread.start()

