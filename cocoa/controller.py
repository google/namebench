#
#  controller.py
#  namebench
#
#  Created by Thomas Stromberg on 9/10/09.
#  Copyright (c) 2009 __MyCompanyName__. All rights reserved.
#

from objc import YES, NO, IBAction, IBOutlet
from Foundation import *
from AppKit import *
import datetime
import urllib
import time
import webbrowser
import tempfile
import sys
import os
import re

# TODO(tstromberg): Research best practices for bundling cocoa frontends.
NB_SOURCE = os.getcwd()[0:os.getcwd().index('/cocoa/')]
sys.path.append(NB_SOURCE)
from lib import config
from lib import nameserver_list
from lib import third_party
from lib import benchmark
from lib import util

class controller(NSWindowController):
  nameserver_form = IBOutlet()
  include_global = IBOutlet()
  include_regional = IBOutlet()
  data_source = IBOutlet()
  selection_mode = IBOutlet()
  num_tests = IBOutlet()
  num_runs = IBOutlet()
  
  status = IBOutlet()
  spinner = IBOutlet()

  def updateStatus(self, message, count=None, total=None):
    if total and count:
      state = '%s [%s/%s]' % (message, count, total)
    elif count:
      state = '%s%s' % (message, '.' * count)
    else:
      state = message

    NSLog(state)
    self.status.setStringValue_(state)

  @IBAction   
  def startJob_(self, sender):
    self.ProcessForm()
    self.updateStatus('Starting benchmark thread')	
    t = NSThread.alloc().initWithTarget_selector_object_(self, self.benchmarkThread, None)
    t.start()
    
  def ProcessForm(self):  
    self.updateStatus('Processing form inputs')	
    if self.include_global.stringValue() == '0':
      self.primary = []
    elif self.include_regional.stringValue() == '0':
      self.secondary = []
      
    for ns in re.split('[, ]+', self.nameserver_form.stringValue()):
      self.primary.append((ns,ns))
      
    self.options.test_count = int(self.num_tests.stringValue())
    self.options.run_count = int(self.num_runs.stringValue())
    self.updateStatus("%s tests, %s runs" % (self.options.test_count, self.options.run_count))

    self.updateStatus('Building nameserver objects')
    self.nameservers = nameserver_list.NameServers(
        self.primary, 
        self.secondary,
        num_servers=self.options.num_servers,
        timeout=self.options.timeout,
        health_timeout=self.options.health_timeout,
        status_callback=self.updateStatus
    )
    self.nameservers.cache_dir = tempfile.gettempdir()    
    if len(self.nameservers) > 1:
      self.nameservers.thread_count = int(self.options.thread_count)
      self.nameservers.cache_dir = tempfile.gettempdir()
  
  def benchmarkThread(self):
    pool = NSAutoreleasePool.alloc().init()
    self.spinner.startAnimation_(self)
    self.updateStatus('Preparing benchmark')
    self.nameservers.FindAndRemoveUndesirables()
    bmark = benchmark.Benchmark(self.nameservers, test_count=self.options.test_count, run_count=self.options.run_count,
                                status_callback=self.updateStatus)
    bmark.CreateTestsFromFile('%s/data/alexa-top-10000-global.txt' % NB_SOURCE)

    # Patch in our graphical updateStatus method
    bmark.updateStatus = self.updateStatus
    self.updateStatus('Running...')
    bmark.Run()
    output_dir = os.path.join(os.getenv('HOME'), 'Desktop')
    output_base = 'namebench_%s' % datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d %H:%m')
    report_path = os.path.join(output_dir, '%s.html' % output_base)
    self.updateStatus('Saving report to %s' % report_path)
    f = open(report_path, 'w')
    bmark.CreateReport(format='html', output_fp=f)
    f.close()
    csv_path = os.path.join(output_dir, '%s.csv' % output_base)
    self.updateStatus('Saving detailed results to %s' % csv_path)    
    bmark.SaveResultsToCsv(csv_path)
    self.updateStatus('Creating report URL for %s' % report_path)
    url = 'file://' + urllib.quote(report_path)
    success = webbrowser.open(url)
    if not success:
      self.displayError("Unable to open web-browser", "Please open %s manually." % report_path)
      
    self.spinner.stopAnimation_(self)
    best = bmark.BestOverallNameServer()
    self.updateStatus('Complete! %s [%s] is the best.' % (best.name, best.ip))
    pool.release()
  
  def displayError(self, msg, details):
    alert = NSAlert.alloc().init()
    alert.setMessageText_(msg)
    alert.setInformativeText_(details)
    #alert.setAlertStyle(NSInformationalAlertStyle)
    buttonPressed = alert.runModal()

  def awakeFromNib(self):
    conf_file = os.path.join(NB_SOURCE, 'namebench.cfg')
    (self.options, self.primary, self.secondary) = config.GetConfiguration(filename=conf_file)
    self.updateStatus('Ready')
    self.setFormDefaults()
    
  def setFormDefaults(self):
    nameservers_string = ', '.join(util.InternalNameServers())
    self.nameserver_form.setStringValue_(nameservers_string)
    self.selection_mode.removeAllItems()
    self.selection_mode.addItemsWithTitles_(['Weighted'])
    self.data_source.removeAllItems()
    self.data_source.addItemsWithTitles_(['Alexa'])
    self.num_tests.setStringValue_(self.options.test_count)
    self.num_runs.setStringValue_(self.options.run_count)

