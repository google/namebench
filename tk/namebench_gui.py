#!/usr/bin/env python
import threading
import time
from Tkinter import *

NB_SOURCE = '/home/tstromberg/namebench'
sys.path.append(NB_SOURCE)

from lib import benchmark
from lib import nameserver_list

class BenchmarkThread(threading.Thread):
  """Quickly test the health of many nameservers with multiple threads."""

  def __init__(self, nameservers, status_callback=None):
    threading.Thread.__init__(self)
    self.nameservers = []
    self.status_callback = status_callback
    for ip in nameservers:
      self.nameservers.append((ip, ip))

  def updateStatus(self, msg, count=None, total=None):
    if hasattr(self, 'status_callback') and self.status_callback:
      self.status_callback(msg, count=count, total=total)
    else:
      print msg

  def run(self):
    self.updateStatus('Preparing benchmark')
    nameservers = nameserver_list.NameServers(self.nameservers, include_internal=True,
                                              status_callback=self.status_callback)
    bmark = benchmark.Benchmark(nameservers, test_count=110, run_count=1,
                                status_callback=self.status_callback)
    bmark.CreateTestsFromFile('%s/data/alexa-top-10000-global.txt' % NB_SOURCE)
    bmark.Run()
    bmark.CreateReport()
    bmark.SaveResultsToCsv('output.csv')
    best = bmark.BestOverallNameServer()
    self.updateStatus('%s looks pretty good' % best)

class GridDemo(Frame):
  def __init__(self):
    Frame.__init__(self)
    self.DisplayInterface()

  def DisplayInterface(self):
    self.primary = StringVar()
    self.status = StringVar()

    self.master.title("namebench")
    Label(self.master, text="Primary DNS").grid(row=0)
    primary = Entry(self.master, bg="white", textvariable=self.primary)
    checkbutton = Checkbutton(self.master, text="Include secondary")
    button = Button(self.master, text = "Start", command=self.StartBenchmark)
    status = Label(self.master, textvariable=self.status)
    primary.grid(row=0, column=1)
    checkbutton.grid(columnspan=2, sticky=W)
    status.grid(row=10, column=1, columnspan=2)
    button.grid(row=10, column=3)
    self.updateStatus('Ready')

  def updateStatus(self, message, count=None, total=None):
    if total and count:
      state = '%s [%s/%s]' % (message, count, total)
    elif count:
      state = '%s%s' % (message, '.' * count)
    else:
      state = message

    print state
    self.status.set(state)

  def StartBenchmark(self):
    self.updateStatus('%s?' % self.primary.get())
    servers = self.primary.get().split()
    self.status.set('Starting: servers=%s' % servers)
    thread = BenchmarkThread(servers, status_callback=self.updateStatus)
    thread.start()

def main():
   GridDemo().mainloop()

if __name__ == "__main__":
   main()