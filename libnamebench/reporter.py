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

"""Report generation class."""

import csv
import datetime
import operator
import os.path
import platform

# external dependencies (from third_party)
try:
  import third_party
except ImportError:
  pass

import jinja2
import simplejson

from . import charts
from . import nameserver
from . import selectors
from . import util


FAQ_MAP = {
  'NXDOMAIN': 'http://code.google.com/p/namebench/wiki/FAQ#What_does_"NXDOMAIN_hijacking"_mean?',
  'Incorrect result': 'http://code.google.com/p/namebench/wiki/FAQ#What_does_"Incorrect_result_for..."_mean?'
}

# Only bother showing a percentage if we have this many tests.
MIN_RELEVANT_COUNT = 50

class ReportGenerator(object):
  """Generate reports - ASCII, HTML, etc."""

  def __init__(self, config, nameservers, results, index=None, geodata=None,
               status_callback=None):
    """Constructor.

    Args:
      nameservers: A list of nameserver objects to include in the report.
      results: A dictionary of results from Benchmark.Run()
      index: A dictionary of results for index hosts.
    """
    self.nameservers = nameservers
    self.results = results
    self.index = index
    self.config = config
    self.geodata = geodata
    self.status_callback = status_callback

  def msg(self, msg, **kwargs):
    if self.status_callback:
      self.status_callback(msg, **kwargs)

  def ComputeAverages(self):
    """Process all runs for all hosts, yielding an average for each host."""
    for ns in self.results:
      failure_count = 0
      nx_count = 0
      run_averages = []

      for test_run in self.results[ns]:
        # x: record, req_type, duration, response
        total_count = len(test_run)
        failure_count += len([x for x in test_run if not x[3]])
        nx_count += len([x for x in test_run if x[3] and not x[3].answer])
        duration = sum([x[2] for x in test_run])
        run_averages.append(duration / len(test_run))

      # This appears to be a safe use of averaging averages
      overall_average = util.CalculateListAverage(run_averages)
      (fastest, slowest) = self.FastestAndSlowestDurationForNameServer(ns)

      yield (ns, overall_average, run_averages, fastest, slowest,
             failure_count, nx_count, total_count)

  def FastestAndSlowestDurationForNameServer(self, ns):
    """For a given nameserver, find the fastest/slowest non-error durations."""

    fastest_duration = 2**32
    slowest_duration = -1
    
    for test_run_results in self.results[ns]:
      for (host, req_type, duration, response, error_msg) in test_run_results:
        if response and response.answer:
          if duration < fastest_duration:
            fastest_duration = duration
        if duration > slowest_duration:
          slowest_duration = duration
    return (fastest_duration, slowest_duration)

  def FastestNameServerResult(self):
    """Process all runs for all hosts, yielding an average for each host."""
    # TODO(tstromberg): This should not count queries which failed.
    fastest = [(ns, self.FastestAndSlowestDurationForNameServer(ns)[0]) for ns in self.results]
    return sorted(fastest, key=operator.itemgetter(1))

  def BestOverallNameServer(self):
    sorted_averages = sorted(self.ComputeAverages(), key=operator.itemgetter(1))
    hosts = [ x[0] for x in sorted_averages ]
    for host in [ x[0] for x in sorted_averages ]:
      if not host.is_error_prone:
        return host
    # return something if none of them are good.
    return hosts[0]

  def NearestNameServers(self, count=2):
    min_responses = sorted(self.FastestNameServerResult(),
                           key=operator.itemgetter(1))
    return [x[0] for x in min_responses][0:count]

  def _LowestLatencyAsciiChart(self):
    """Return a simple set of tuples to generate an ASCII chart from."""
    fastest = self.FastestNameServerResult()
    slowest_result = fastest[-1][1]
    chart = []
    for (ns, duration) in fastest:
      textbar = util.DrawTextBar(duration, slowest_result)
      chart.append((ns.name, textbar, duration))
    return chart

  def _MeanRequestAsciiChart(self):
    sorted_averages = sorted(self.ComputeAverages(), key=operator.itemgetter(1))
    max_result = sorted_averages[-1][1]
    chart = []
    for result in sorted_averages:
      (ns, overall_mean) = result[0:2]
      textbar = util.DrawTextBar(overall_mean, max_result)
      chart.append((ns.name, textbar, overall_mean))
    return chart

  def CreateReport(self, format='ascii', output_fp=None, csv_path=None):
    lowest_latency = self._LowestLatencyAsciiChart()
    mean_duration = self._MeanRequestAsciiChart()
    sorted_averages = sorted(self.ComputeAverages(), key=operator.itemgetter(1))

    runs_data = [(x[0].name, x[2]) for x in sorted_averages]
    mean_duration_url = charts.PerRunDurationBarGraph(runs_data)
    min_duration_url = charts.MinimumDurationBarGraph(self.FastestNameServerResult())
    distribution_url_200 = charts.DistributionLineGraph(self.DigestedResults(),
                                                        scale=200)

    # timeout in ms, scaled to the non-adjusted timeout
    max_timeout = self.config.timeout * 1000
    distribution_url = charts.DistributionLineGraph(self.DigestedResults(), scale=max_timeout)
    best = self.BestOverallNameServer()
    nearest = [x for x in self.NearestNameServers(3) if x.ip != best.ip][0:2]
    recommended = [best] + nearest

    nameserver_details = list(sorted_averages)
    for ns in self.nameservers:
      if ns.disabled:
        nameserver_details.append((ns, 0.0, [], 0, 0, 0, 0))

      # TODO(tstromberg): Do this properly without injecting variables into the nameserver object.
      # Tuples: Note, URL
      ns.notes = []
      if ns.system_position == 0:
        ns.notes.append(('The current preferred DNS server.', None))
      elif ns.system_position:
        ns.notes.append(('A backup DNS server for this system.', None))
      if ns.is_error_prone:
        ns.notes.append(('%0.0f queries to this host failed' % ns.error_rate, None))
      if ns.disabled:
        ns.notes.append((ns.disabled, None))
      else:
        for warning in ns.warnings:
          use_url = None
          for keyword in FAQ_MAP:
            if keyword in warning:
              use_url = FAQ_MAP[keyword]
          ns.notes.append((warning, use_url))

    builtin_servers = util.InternalNameServers()
    if builtin_servers:
      system_primary = builtin_servers[0]
    else:
      system_primary = False
    other_records = [ x for x in nameserver_details if x[0] != best and not x[0].disabled and not x[0].is_error_prone ]

    if other_records:
      # First try to compare against our primary DNS
      comparison_record = [x for x in other_records if x[0].system_position == 0]
      # Then the fastest "primary"
      if not comparison_record:
        comparison_record = [x for x in other_records if x[0].is_preferred]
      # Fall back to the second fastest of any type.
      if not comparison_record:
        comparison_record = other_records

      percent = ((comparison_record[0][1] / nameserver_details[0][1])-1) * 100
      if nameserver_details[0][-1] >= MIN_RELEVANT_COUNT:
        comparison = {
          'title': "%0.0f%%" % percent,
          'subtitle': 'Faster',
          'ns': comparison_record[0][0]
        }
      else:
        comparison = {
          'title': 'Undecided',
          'subtitle': 'Too few tests (try %s)' % MIN_RELEVANT_COUNT,
          'ns': None
        }
    else:
      comparison = {
        'title': None,
        'subtitle': None,
        'ns': nameserver_details[0][0]
      }

    # Fragile, makes assumption about the CSV being in the same path as the HTML file
    if csv_path:
      csv_link = os.path.basename(csv_path)
    else:
      csv_link = None

    template_name = '%s.tmpl' % format
    template_path = util.FindDataFile(os.path.join('templates', template_name))
    filtered_config = self.FilteredConfig()
    template_dir = os.path.dirname(template_path)
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))
    template = env.get_template(template_name)
#    self.msg('Rendering template: %s' % template_name)
    rendered = template.render(
        system_primary=system_primary,
        timestamp = datetime.datetime.now(),
        lowest_latency=lowest_latency,
        best=best,
        version=self.config.version,
        comparison=comparison,
        config=filtered_config,
        mean_duration=mean_duration,
        nameserver_details=nameserver_details,
        mean_duration_url=mean_duration_url,
        min_duration_url=min_duration_url,
        distribution_url=distribution_url,
        distribution_url_200=distribution_url_200,
        recommended=recommended,
        csv_link=csv_link
    )
    if output_fp:
      output_fp.write(rendered)
      output_fp.close()
    else:
      return rendered

  def FilteredConfig(self):
    """Generate a watered down config listing for our report."""
    keys = [x for x in dir(self.config) if not x.startswith('_') and x != 'config' ]
    config_items = []
    for key in keys:
      value = getattr(self.config, key)
      # > values are ConfigParser internals. None values are just noise.
      if isinstance(value, int) or isinstance(value, float) or isinstance(value, str):
        config_items.append((key, value))
    return sorted(config_items)

  def DigestedResults(self):
    """Return a tuple of nameserver and all associated durations."""
    duration_data = []
    for ns in self.results:
      durations = []
      for test_run_results in self.results[ns]:
        durations += [x[2] for x in test_run_results]
      duration_data.append((ns, durations))
    return duration_data

  def _CreateSharingData(self):
    config = dict(self.FilteredConfig())
    config['platform'] = (platform.system(), platform.release())
    config['python'] = platform.python_version_tuple()

    nsdata_list = []
    sorted_averages = sorted(self.ComputeAverages(), key=operator.itemgetter(1))
    placed_at = -1
    
    for (ns, avg, run_averages, fastest, slowest, failure_count, nx_count, total_count) in sorted_averages:
      placed_at += 1
      
      durations = []
      for test_run in self.results[ns]:
        durations.append([x[2] for x in self.results[ns][0]])

      # Get the meat out of the index data.
      index = []
      if self.index:
        for host, req_type, duration, response, unused_x in self.index[ns]:
          answer_count, ttl = self._ResponseToCountTtlText(response)[0:2]
          index.append((host, req_type, duration, answer_count, ttl))

      masked_ip, masked_name = util.MaskPrivateIP(ns.ip, ns.name)
      nsdata = {
        'ip': masked_ip,
        'name': masked_name,
        'sys_position': ns.system_position,
        'position': placed_at,
        'averages': run_averages,
        'min': fastest,
        'max': slowest,
        'failed': failure_count,
        'nx': nx_count,
        'durations': durations,
        # No need to use the second part of the tuple (URL)
        'notes': [ x[0] for x in ns.notes ],
        'index': index
      }
      nsdata_list.append(nsdata)
      
    return {'config': config, 'nameservers': nsdata_list, 'geodata': self.geodata}
    
  def CreateJsonData(self):
    sharing_data = self._CreateSharingData()
    return simplejson.dumps(sharing_data)

  def _ResponseToCountTtlText(self, response):
    """For a given DNS response, parse the most important details out.

    Args:
      response: DNS response

    Returns:
      tuple of (answer_count, ttl, answer_text)
    """

    answer_text = ''
    answer_count = -1
    ttl = -1
    if response:
      if response.answer:
        answer_count = len(response.answer)
        ttl = response.answer[0].ttl
      answer_text = nameserver.ResponseToAscii(response)
    return (answer_count, ttl, answer_text)


  def SaveResultsToCsv(self, filename):
    """Write out a CSV file with detailed results on each request.

    Args:
      filename: full path on where to save results (string)

    Sample output:
    nameserver, test_number, test, type, duration, answer_count, ttl
    """
    self.msg("Opening %s for write" % filename, debug=True)
    csv_file = open(filename, 'w')
    output = csv.writer(csv_file)
    output.writerow(['IP', 'Name', 'Test_Num', 'Record',
                     'Record_Type', 'Duration', 'TTL', 'Answer_Count',
                     'Response'])
    for ns in self.results:
      self.msg("Saving detailed data for %s" % ns, debug=True)
      for (test_run, test_results) in enumerate(self.results[ns]):
        for (record, req_type, duration, response, error_msg) in test_results:
          (answer_count, ttl, answer_text) = self._ResponseToCountTtlText(response)
          output.writerow([ns.ip, ns.name, test_run, record, req_type, duration,
                           ttl, answer_count, answer_text, error_msg])
    csv_file.close()
    self.msg("%s saved." % filename, debug=True)
    
