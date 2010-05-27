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

import re
import tempfile
import urllib

# external dependencies (from third_party)
try:
  import third_party
except ImportError:
  pass

import httplib2
import simplejson

import util
    

def GetFromGoogleLocAPI():
  """Use the Google Loc JSON API from Google Gears.
  
  NOTE: This is in violation of the Gears Terms of Service. See:  
  http://code.google.com/p/gears/wiki/GeolocationAPI
  
  This method does however return the most accurate results.
  """
  h = httplib2.Http(tempfile.gettempdir(), timeout=10)
  url = 'http://www.google.com/loc/json'
  post_data = { 'request_address': 'true', 'version': '1.1.0', 'source': 'namebench ' }
  resp, content = h.request(url, 'POST', simplejson.dumps(post_data))
  try:
    data = simplejson.loads(content)['location']
    return {
      'region_name': data['address'].get('region'),
      'country_name': data['address'].get('country'),
      'country_code': data['address'].get('country_code'),
      'city': data['address'].get('city'),
      'latitude': data['latitude'],
      'longitude': data['longitude'],
      'source': 'gloc'
    }
  except:
    print "* Failed to use GoogleLocAPI: %s" % util.GetLastExceptionString()
    return {}

def GetFromMaxmindJSAPI():
  h = httplib2.Http(tempfile.gettempdir(), timeout=10)
  resp, content = h.request("http://j.maxmind.com/app/geoip.js", 'GET')
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
    json_data = GetFromGoogleLocAPI()
    if not json_data:
      json_data = GetFromMaxmindJSAPI()
      
    # Make our data less accurate. We don't need any more than that.
    json_data['latitude'] = '%.3f' % float(json_data['latitude'])
    json_data['longitude'] = '%.3f' % float(json_data['longitude'])
    return json_data
  except:
    print "Failed to get Geodata: %s" % util.GetLastExceptionString()
    return {}
