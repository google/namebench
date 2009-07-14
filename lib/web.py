#!/usr/bin/python
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
