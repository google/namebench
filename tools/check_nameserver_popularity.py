#!/usr/bin/env python
import os
import sys
import pickle
import time
import traceback
import yahoo.search
from yahoo.search.web import WebSearch

APP_ID = 'P5ihFKzV34G69QolFfb3nN7p0rSsYfC9tPGq.IUS.NLWEeJ14SG9Lei0rwFtgwL8cDBrA6Egdw--'
QUERY_MODIFIERS = '-site:txdns.net -syslog -"4.2.2.1" -site:cqcounter.com -site:flow.nttu.edu.tw -site:websiteoutlook.com -site:ipgeolocator.com -site:tdyndns.org -site:ebrara.com -site:onsamehost.com -site:ipaddresscentral.com -site:quia.jp -inetnum -site:domaintools.com -site:domainbyip.com -site:pdos.csail.mit.edu  -statistics  -"country name" -"Q_RTT" -site:botsvsbrowsers.com -"ptr record" -site:ip-db.com -site:chaip.com.cn -site:lookup365.com -"IP Country" -site:iptoolboxes.com -"Unknown Country" -"Q_RTT" -amerika -whois -Mozilla -site:domaincrawler.com -site:geek-tools.org -site:visualware.com -site:robtex.com -site:domaintool.se -site:opendns.se -site:ungefiltert-surfen.de'
CACHE_DIR = os.getenv('HOME') + '/.ycache'

for ip in sys.argv[1:]:
  query = '"%s" %s' % (ip, QUERY_MODIFIERS)
  cache_path = os.path.join(CACHE_DIR, ip)
  if os.path.exists(cache_path + '.pickle'):
    print '%s in cache' % ip
  else:
    if os.path.exists(cache_path):
      total = open(cache_path).read()
      print total
      if total == '0':
        continue
    try:
      srch = WebSearch(APP_ID, query=query, results=50)
      results = srch.parse_results()
      total = len(results.results)
      f = open(cache_path, 'w')
      f.write(str(total))
      f.close()
      
      pf = open(cache_path + '.pickle', 'w')
      pickle.dump(results.results, pf)
      pf.close()
      
      print '%s = %s' % (ip, total)
      for result in results.results:
        try:
          print '  - %s: %s' % (result['Url'], result['Title'])
        except UnicodeEncodeError:
          print '  - %s' % result['Url']#      print results.results
    except yahoo.search.SearchError:
      print "%s failed" % (ip)
      print sys.exc_info()
    time.sleep(0.5)
