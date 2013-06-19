# Copyright 2010 Google Inc. All Rights Reserved.
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

"""Class used for determining GeoIP location."""


import csv
import json
import math
import re
import tempfile

from . import util

# third_party dependencies
import httplib2

def GetFromMaxmindJSAPI():
  h = httplib2.Http(tempfile.gettempdir(), timeout=10)
  unused_resp, content = h.request('http://j.maxmind.com/app/geoip.js', 'GET')
  keep = ['region_name', 'country_name', 'city', 'latitude', 'longitude', 'country_code']
  results = dict([x for x in re.findall("geoip_(.*?)\(.*?\'(.*?)\'", content) if x[0] in keep])
  results.update({'source': 'mmind'})
  if results:
    return results
  else:
    return {}


def GetGeoData():
  """Get geodata from any means necessary. Sanitize as necessary."""
  try:
    json_data = GetFromMaxmindJSAPI()

    # Make our data less accurate. We don't need any more than that.
    json_data['latitude'] = '%.3f' % float(json_data['latitude'])
    json_data['longitude'] = '%.3f' % float(json_data['longitude'])
    return json_data
  except:
    print(('Failed to get Geodata: %s' % util.GetLastExceptionString()))
    return {}

def GetInfoForCountry(country_name_or_code):
  """Get code, name, lat and lon for a given country name or code."""
  match = False
  partial_match = False
  if not country_name_or_code:
    return None

  if len(country_name_or_code) == 2:
    country_code = country_name_or_code.upper()
    country_name = False
  else:
    country_name = country_name_or_code
    country_code = False

  for row in ReadCountryData():
    lat, lon = row['coords'].split(',')
    if country_code:
      if row['code'] == country_code:
        return row['code'], row['name'], lat, lon
    elif country_name:
      if re.match("^%s$" % country_name, row['name'], re.I):
        return row['code'], row['name'], lat, lon
      elif re.search('^%s \(' % country_name, row['name'], re.I):
          return row['code'], row['name'], lat, lon
      elif re.search('\(%s\)' % country_name, row['name'], re.I):
        return row['code'], row['name'], lat, lon
      elif re.match("^%s" % country_name, row['name'], re.I):
        match = (row['code'], row['name'], lat, lon)
      elif re.search(country_name, row['name'], re.I):
        partial_match = (row['code'], row['name'], lat, lon)

  if match:
    print(("Could not find explicit entry for '%s', good match: %s" % (country_name_or_code, match)))
    return match
  elif partial_match:
    print(("Could not find explicit entry for '%s', partial match: %s" % (country_name_or_code, partial_match)))
    return partial_match
  else:
    print(("'%s' does not match any countries in our list." % country_name_or_code))
    return (None, None, None, None)

def ReadCountryData(filename='data/countries.csv'):
  """Read country data file, yielding rows of information."""
  country_file = util.FindDataFile(filename)
  for row in csv.DictReader(open(country_file), fieldnames=['name', 'code', 'coords']):
    yield row
