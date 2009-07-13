#!/usr/bin/python
from itty import itty
from lib import benchmark

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
