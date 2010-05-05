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

# external dependencies (from third_party)
try:
  import third_party
except ImportError:
  pass

import httplib2
import simplejson

    
def GetFromGoogleJSAPI():
  """Using the Google JSAPI API, get the geodata for the current IP.
  
  NOTE: This will return the geodata for the proxy server in use!
  """
  h = httplib2.Http(tempfile.gettempdir(), timeout=10)
  resp, content = h.request("http://google.com/jsapi", 'GET')  
  geo_matches = re.search('google.loader.ClientLocation = ({.*?});', content)  
  if geo_matches:
    return simplejson.loads(geo_matches.group(1))
  else:
    return {}
