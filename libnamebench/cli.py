#!/usr/bin/env python
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


"""Simple DNS server comparison benchmarking tool.

Designed to assist system administrators in selection and prioritization.
"""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import datetime
import math
import sys

import base_ui
import conn_quality
import nameserver_list


class NameBenchCli(base_ui.BaseUI):
  """A command-line implementation of the namebench workflow."""

  def __init__(self, options):
    self.options = options
    self.last_msg = (None, None, None, None)
    self.last_msg_count_posted = 0
    super(NameBenchCli, self).__init__()

  def UpdateStatus(self, msg, count=None, total=None, error=False, debug=False):
    """Status updates for the command-line. A lot of voodoo here."""
    if self.last_msg == (msg, count, total, error):
      return None

    if debug:
      return None

    if error:
      print
      print '* ERROR: %s' % msg
      sys.exit(2)
    elif not total:
      self.last_msg_count_posted = 0
      sys.stdout.write('- %s\n' % msg)
    elif self.last_msg[0] != msg:
      self.last_msg_count_posted = 0
      sys.stdout.write('- %s: %s/%s' % (msg, count, total))
      last_count = 0
    else:
      last_count = self.last_msg[1]

    if total:
      if count and (count - last_count > 0):
        # Write a few dots to catch up to where we should be.
        catch_up = int(math.ceil((count - last_count) / 2.0))
        sys.stdout.write('.' * catch_up)

      if count == total:
       sys.stdout.write('%s/%s\n' % (count, total))
      elif total > 25 and count and (count - self.last_msg_count_posted > (total * 0.20)):
        sys.stdout.write(str(count))
        self.last_msg_count_posted = count
    sys.stdout.flush()
    self.last_msg = (msg, count, total, error)

  def RunAndOpenReports(self):
    self.RunBenchmark()
    print "\n%s\n" % self.reporter.CreateReport(format='ascii')
    self.CreateReports()
    if self.options.open_webbrowser:
      self.DisplayHtmlReport()

  def Execute(self):
    """Called by namebench.py to start the show."""
    print('namebench %s - %s (%s) on %s' %
          (self.options.version, self.options.input_source or 'best source',
           self.options.select_mode, datetime.datetime.now()))
    print ('threads=%s/%s queries=%s runs=%s timeout=%s health_timeout=%s servers=%s' %
           (self.options.health_thread_count, self.options.benchmark_thread_count,
            self.options.query_count,
            self.options.run_count, self.options.timeout,
            self.options.health_timeout, self.options.num_servers))
    print '-' * 78

    try:
      self.PrepareNameServers()
    except nameserver_list.TooFewNameservers:
      print "You need to specify some DNS servers to benchmark. Try:"
      print ""
      print "namebench.py -a                  # Benchmark all available DNS servers"
      print "namebench.py -s                  # Benchmark current system DNS servers"
      print "namebench.py -r                  # Benchmark regional DNS servers only"
      print "namebench.py -g                  # Benchmark global DNS servers only"
      print "namebench.py 8.8.8.8 10.0.0.1    # Benchmark just these two servers"
      print ""
      print "For more assistance, get help via namebench.py -h"
      sys.exit(1)
    try:
      self.LoadDataSources()
      self.PrepareTestRecords()
      print '-' * 78
      self.CheckNameServerHealth()
      print 'Final list of nameservers considered:'
      print '-' * 78
      for n in self.nameservers.SortByFastest():
        print '%-15.15s %-18.18s %-4.0fms | %s' % (n.ip, n.name, n.check_average,
                                                   n.warnings_string)
      print ''

      print ''
      self.PrepareBenchmark()
      self.RunAndOpenReports()
    except (nameserver_list.OutgoingUdpInterception,
            nameserver_list.TooFewNameservers,
            conn_quality.OfflineConnection):
      (exc_type, exception) = sys.exc_info()[0:2]
      self.UpdateStatus("%s - %s" % (exc_type, exception), error=True)



