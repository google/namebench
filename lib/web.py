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


# NOTE: This code is very experimental, and unlikely to be usable in
# any form at this stage.


import threading
import webbrowser

from itty import itty
from lib import benchmark

TEXT_WEB_BROWSERS = ('links', 'elinks', 'w3m', 'lynx')
DEFAULT_URL = 'http://127.0.0.1:8080'


class WebServerThread (threading.Thread):
  """Run a webserver in a background thread."""
  def run(self):
    web.start()

def OpenBrowserWindow():
  for browser in TEXT_WEB_BROWSERS:
    if browser in webbrowser._tryorder:
      webbrowser._tryorder.remove(browser)

  if webbrowser._tryorder:
    webbrowser.open('http://127.0.0.1:8080/', new=1, autoraise=1)
  else:
    print 'Could not find your browser. Please open one and visit %s' % DEFAULT_URL

#NB = benchmark.NameBench('data/alexa-top-10000.txt', run_count=5,
#                             test_count=2)

@itty.get('/')
def index(request):
    nameservers = NB.FindUsableNameServers()
    return str(nameservers)


@itty.get('/nameservers')
def nameservers(request):
  return ','.join(NB.nameservers.keys)

def start():
  itty.run_itty()
  print "Server is running"
