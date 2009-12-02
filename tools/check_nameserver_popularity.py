#!/usr/bin/env python
import os
import sys
import time
import traceback
from yahoo.search.web import WebSearch

APP_ID = 'P5ihFKzV34G69QolFfb3nN7p0rSsYfC9tPGq.IUS.NLWEeJ14SG9Lei0rwFtgwL8cDBrA6Egdw--'
QUERY_MODIFIERS = ' -site:ebrara.com -statistics  -"country name" -"Q_RTT" -site:botsvsbrowsers.com -"ptr record" -site:ip-db.com -site:chaip.com.cn -site:lookup365.com -statistics -site:iptoolboxes.com -"Unknown Country" -"Q_RTT" -"DNS Server List - Name Server List" -whois -"MSIE 6.0" -site:domaincrawler.com -site:geek-tools.org -site:visualware.com -site:robtex.com -site:domaintool.se -site:opendns.se -site:ungefiltert-surfen.de'
CACHE_DIR = os.getenv('HOME') + '/.ycache'

for ip in sys.argv[1:]:
  query = '"%s" %s' % (ip, QUERY_MODIFIERS)
  cache_path = os.path.join(CACHE_DIR, ip)
  if os.path.exists(cache_path):
    continue
    print '%s in cache' % ip
  else:
  #  print query
    try:
      srch = WebSearch(APP_ID, query=query, results=50)
      results = srch.parse_results()
      total = len(results.results)
      print '%s = %s' % (ip, total)
      f = open(cache_path, 'w')
      f.write(str(total))
      f.close()
    except:
      print "%s failed" % (ip)
#      print traceback.print_last()
    time.sleep(15)
