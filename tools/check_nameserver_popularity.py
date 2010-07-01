#!/usr/bin/env python
import os
import sys
import pickle
import time
import traceback
import yahoo.search
from yahoo.search.web import WebSearch

APP_ID = 'P5ihFKzV34G69QolFfb3nN7p0rSsYfC9tPGq.IUS.NLWEeJ14SG9Lei0rwFtgwL8cDBrA6Egdw--'
QUERY_MODIFIERS = '-site:txdns.net -site:sitedossier.com -mx -site:dataopedia.com -site:l0t3k.net -syslog -"4.2.2.1" -site:cqcounter.com -site:flow.nttu.edu.tw -site:websiteoutlook.com -site:ipgeolocator.com -site:tdyndns.org -site:ebrara.com -site:onsamehost.com -site:ipaddresscentral.com -site:quia.jp -inetnum -site:domaintools.com -site:domainbyip.com -site:pdos.csail.mit.edu  -statistics  -"country name" -"Q_RTT" -site:botsvsbrowsers.com -"ptr record" -site:ip-db.com -site:chaip.com.cn -site:lookup365.com -"IP Country" -site:iptoolboxes.com -"Unknown Country" -"Q_RTT" -amerika -whois -Mozilla -site:domaincrawler.com -site:geek-tools.org -site:visualware.com -site:robtex.com -site:domaintool.se -site:opendns.se -site:ungefiltert-surfen.de -site:datakitteh.org -"SLOVAKIA (SK)" -"IP Search" -site:www.medicore.com.ua -site:dig.similarbase.com -site:ipcorporationwiki.com -site:coolwhois.com -site:corporationwiki.com -site:iptool.us'
CACHE_DIR = os.getenv('HOME') + '/.ycache'

def CheckPopularity(ip):
  # DUH
  cache_path = os.path.join(CACHE_DIR, ip) + '.pickle.pickle'
  if os.path.exists(cache_path):
    f = open(cache_path)
    return pickle.load(f)
  else:
    print "miss: %s" % ip
    try:
      query = '"%s" %s' % (ip, QUERY_MODIFIERS)
      srch = WebSearch(APP_ID, query=query, results=50)
      results = srch.parse_results()
      pf = open(cache_path, 'w')
      pickle.dump(results.results, pf)
      pf.close()
      return results
    except yahoo.search.SearchError:
      print "%s failed" % (ip)
      return []

if __name__ == "__main__":
  pass
