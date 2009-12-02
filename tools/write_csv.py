#!/usr/bin/python

import csv
import sys
import pygeoip
sys.path.append('..')
sys.path.append('/Users/tstromberg/namebench')
import third_party
from libnamebench import nameserver
from libnamebench import config
from libnamebench import util

geo_city = pygeoip.GeoIP('/usr/local/share/GeoLiteCity.dat')
output = csv.writer(open('output.csv', 'w'))

for line in sys.stdin:
  (ip, desc) = line.split('=')[0:2]
  desc = desc.rstrip()
  ns = nameserver.NameServer(ip)
  details = geo_city.record_by_addr(ns.ip)
  try:
    city = details.get('city', '')
    country_code = details.get('country_code', '')
    country = details.get('country_name', '')
    region = details.get('region_name', '')
  except:
    city = ''
    country_code = ''
    country = ''
    region = ''

  if '(' in desc:
    hostname = desc.split(' ')[0]
    desc = ''
  else:
    hostname = ns.hostname

  out_columns = (str(ip), desc, hostname, country_code, city, region, country)
  print out_columns
  output.writerow(out_columns)
