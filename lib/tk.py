#!/usr/bin/env python
import threading
import time
import webbrowser
import tempfile
import os.path
from Tkinter import *

NB_SOURCE = '/Users/tstromberg/namebench'
sys.path.append(NB_SOURCE)

from lib import benchmark
from lib import nameserver_list

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
    if hasattr(self, 'status_callback') and self.status_callback:
      self.status_callback(msg, count=count, total=total)

  def run(self):
    self.updateStatus('Preparing benchmark')
    nameservers = nameserver_list.NameServers(self.nameservers, include_internal=True,
                                              status_callback=self.status_callback)
    bmark = benchmark.Benchmark(nameservers, test_count=self.tests, run_count=1,
                                status_callback=self.status_callback)
    bmark.CreateTestsFromFile('%s/data/alexa-top-10000-global.txt' % NB_SOURCE)
    bmark.Run()
    best = bmark.BestOverallNameServer()
    self.updateStatus('%s looks pretty good' % best)
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
    self.DisplayInterface()
    
  def Execute(self):
    self.mainloop()

  def DisplayInterface(self):
    self.nameservers = StringVar()
    self.status = StringVar()
    self.num_tests = IntVar()
    self.num_runs = IntVar()
    self.data_source = StringVar()
    self.selection_type = StringVar()
    self.use_global = IntVar()
    self.use_regional = IntVar()

    self.master.title("namebench")
    x_padding=12

    Label(self.master, text="Nameservers").grid(row=0, columnspan=2, sticky=W, padx=x_padding)

    nameservers = Entry(self.master, bg="white", textvariable=self.nameservers, width=50)
    nameservers.grid(row=1, columnspan=2, sticky=W, padx=x_padding+4)

    global_button = Checkbutton(self.master, text="Include global DNS providers (OpenDNS, UltraDNS)", variable=self.use_global)
    global_button.grid(row=2, columnspan=2, sticky=W, padx=x_padding)
    global_button.toggle()

    regional_button = Checkbutton(self.master, text="Include best available regional DNS services", variable=self.use_regional)
    regional_button.grid(row=3, columnspan=2, sticky=W, padx=x_padding)
    regional_button.toggle()

    Label(self.master, text="_" * 50).grid(row=4, columnspan=2)

    Label(self.master, text="Benchmark Data Source").grid(row=5, column=0, sticky=W, padx=x_padding)
    Label(self.master, text="Number of tests").grid(row=5, column=1, sticky=W, padx=x_padding)

    data_source = OptionMenu(self.master, self.data_source, "Alexa Top 10000", "b")
    data_source.grid(row=6, column=0, sticky=W, padx=x_padding)

    num_tests = Entry(self.master, bg="white", textvariable=self.num_tests)
    num_tests.grid(row=6, column=1, sticky=W, padx=x_padding+4)

    Label(self.master, text="Benchmark Data Selection").grid(row=7, column=0, sticky=W, padx=x_padding)
    Label(self.master, text="Number of runs").grid(row=7, column=1, sticky=W, padx=x_padding)

    selection_type = OptionMenu(self.master, self.selection_type, "Weighted", "Random", "Chunk")
    selection_type.grid(row=8, column=0, sticky=W, padx=x_padding)

    num_runs = Entry(self.master, bg="white", textvariable=self.num_runs)
    num_runs.grid(row=8, column=1, sticky=W, padx=x_padding+4)

#    Label(self.master, text="_" * 50).grid(row=14, columnspan=2)

    button = Button(self.master, text = "Start Benchmark", command=self.ProcessForm)
    status = Label(self.master, textvariable=self.status)
    status.grid(row=15, sticky=W, padx=x_padding, pady=8, column=0)
    button.grid(row=15, sticky=E, column=1, padx=x_padding, pady=8)
    self.nameservers.set('192.168.1.1, 10.0.0.0.1')
    self.num_runs.set(1)
    self.selection_type.set('Weighted')
    self.data_source.set('Alexa Top 10000')
    self.num_tests.set(110)
    self.updateStatus('Ready...')

  def updateStatus(self, message, count=None, total=None, error=None):
    if total and count:
      state = '%s [%s/%s]' % (message, count, total)
    elif count:
      state = '%s%s' % (message, '.' * count)
    else:
      state = message

    print state
    self.status.set(state)

  def ProcessForm(self):
    pass

  def StartBenchmark(self):
    self.updateStatus('%s?' % self.primary.get())
    servers = self.primary.get().split()
    self.status.set('Starting: servers=%s' % servers)
    thread = BenchmarkThread(servers, tests=self.tests_num.get(),
                             status_callback=self.updateStatus)
    thread.start()

