# Copyright 2009 Google Inc. All Rights Reserved.

"""Little utility functions."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import nameserver

OPENDNS_NS = '208.67.220.220'


def TimeDeltaToMilliseconds(td):
  """Convert timedelta object to milliseconds."""
  return (td.days*86400000) + (td.seconds*1000) + (td.microseconds/1000.0)


def split_seq(seq, size):
  """Recipe From http://code.activestate.com/recipes/425397/ ."""
  newseq = []
  splitsize = 1.0/size*len(seq)
  for i in range(size):
    newseq.append(seq[int(round(i*splitsize)):int(round((i+1)*splitsize))])
  return newseq


def AreDNSPacketsIntercepted():
  """Check if our packets are actually getting to the correct servers."""

  opendns = nameserver.NameServer(OPENDNS_NS)
  response = opendns.TimedRequest('TXT', 'which.opendns.com.')[0]
  for answer in response.answer:
    if 'I am not an OpenDNS resolver' in answer.to_text():
      return True
  return False
