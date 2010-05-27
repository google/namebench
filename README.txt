Are you a power-user with 5 minutes to spare? Do you want a faster internet
experience?

Try out namebench. It hunts down the fastest DNS servers available for your
computer to use. namebench runs a fair and thorough benchmark using your web
browser history, tcpdump output, or standardized datasets in order to
provide an individualized recommendation. namebench is completely free and
does not modify your system in any way. This project began as a 20% project
at Google.

namebench runs on Mac OS X, Windows, and UNIX, and is available with a
graphical user interface as well as a command-line interface. 

Requirements:

  * Python 2.4 - 2.6. If you are using Mac OS X or Linux, this is
    built-in. Otherwise, visit http://www.python.org/

--[ quick use guide ]---------------------------------------------------------

namebench comes with two interfaces: a simple graphical interface, and a
more advanced command-line interface. If you have downloaded the versions
for Mac OS X and Windows, you will get the graphical interface by default.

Most people will simply want to run this software with no arguments:

  ./namebench.py

On UNIX, if you have python-tk installed, a graphical interface will pop up.
If you would like to force use of the command-line, use -x:

  ./namebench.py -x

If you want to specify an additional set of name services, simply add the IP
to the command-line, or edit namebench.cfg:

  ./namebench.py 10.0.0.1 192.168.0.1

--[ credit ]------------------------------------------------------------------

namebench includes some wonderful third party software:

 * dnspython 1.8.0 (http://www.dnspython.org/)
 * httplib2 0.6.0 (http://code.google.com/p/httplib2/)
 * graphy 1.0 (http://graphy.googlecode.com/)
 * jinja2 2.2.1 (http://jinja.pocoo.org/2/)
 * python 2.5 pkg_resources (http://www.python.org/) 
 * simplejson 2.1.1 (http://code.google.com/p/simplejson/)
 * Crystal SVG icons (http://www.everaldo.com/crystal/)

For licensing information, see the LICENSE file within the appropriate
subdirectory.

--[ options ]-----------------------------------------------------------------

Usage: namebench.py [options]

Options:
  -h, --help            show this help message and exit
  -r RUN_COUNT, --runs=RUN_COUNT
                        Number of test runs to perform on each nameserver.
  -z CONFIG, --config=CONFIG
                        Config file to use.
  -o OUTPUT_FILE, --output=OUTPUT_FILE
                        Filename to write output to
  -t TEMPLATE, --template=TEMPLATE
                        Template to use for output generation (ascii, html,
                        resolv.conf)
  -c CSV_FILE, --csv_output=CSV_FILE
                        Filename to write query details to (CSV)
  -j HEALTH_THREAD_COUNT, --health_threads=HEALTH_THREAD_COUNT
                        # of health check threads to use
  -J BENCHMARK_THREAD_COUNT, --benchmark_threads=BENCHMARK_THREAD_COUNT
                        # of benchmark threads to use
  -P PING_TIMEOUT, --ping_timeout=PING_TIMEOUT
                        # of seconds ping requests timeout in.
  -y TIMEOUT, --timeout=TIMEOUT
                        # of seconds general requests timeout in.
  -Y HEALTH_TIMEOUT, --health_timeout=HEALTH_TIMEOUT
                        health check timeout (in seconds)
  -i INPUT_SOURCE, --input=INPUT_SOURCE
                        Import hostnames from an filename or application
                        (alexa, cachehit, cachemiss, cachemix, camino, chrome,
                        chromium, epiphany, firefox, flock, galeon, icab,
                        internet_explorer, konqueror, midori, omniweb, opera,
                        safari, seamonkey, squid, sunrise)
  -I, --invalidate_cache
                        Force health cache to be invalidated
  -q QUERY_COUNT, --query_count=QUERY_COUNT
                        Number of queries per run.
  -m SELECT_MODE, --select_mode=SELECT_MODE
                        Selection algorithm to use (weighted, random, chunk)
  -s NUM_SERVERS, --num_servers=NUM_SERVERS
                        Number of nameservers to include in test
  -S, --system_only     Only test the currently configured system
  - nameservers.
  -w, --open_webbrowser
                        Opens the final report in your browser
  -u, --upload_results  Upload anonmyized results to SITE_URLl (default:
                        False)
  -U SITE_URL, --site_url=SITE_URL
                        URL to upload results to
                        (http://namebench.appspot.com/)
  -H, --hide_results    Upload results, but keep them hidden from indexes.
  -x, --no_gui          Disable GUI
  -C, --enable-censorship-checks
                        Enable censorship checks
  -6, --ipv6_only       Only include IPv6 name servers
  -O, --only            Only test nameservers passed as arguments

--[ sample output ]-------------------------------------------------------------

namebench 1.3b1 - best history source (automatic) on 2010-05-27 08:34:46.585534
threads=40/2 queries=250 runs=1 timeout=3.5 health_timeout=3.75 servers=11
------------------------------------------------------------------------------
- Reading Top 2,000 Websites (Alexa): data/alexa-top-2000-domains.txt (0.7MB)
- Reading Cache Latency Test (100% hit): data/cache-hit.txt (0.1MB)
- Reading Cache Latency Test (100% miss): data/cache-miss.txt (0.1MB)
- Reading Cache Latency Test (50% hit, 50% miss): data/cache-mix.txt (0.1MB)
- Skipping /home/tstromberg/Library/Application Support/Chromium/Default/History (168d old)
- Generating tests from Top 2,000 Websites (Alexa) (33575 records, selecting 250 automatic)
- Selecting 250 out of 33542 sanitized records (weighted mode).

- Checking query interception status...
- Checking connection quality: 1/3...3/3
- Congestion level is 36.88X (check duration: 1475.29ms)
- Applied 4.50X timeout multiplier due to congestion: 2.2 ping, 3.5 standard, 16.9 health.
- Checking latest sanity reference
- Checking nameserver health (4040 servers)
- Building initial DNS cache for 4040 nameservers (40 threads)
- Checking nameserver availability (40 threads): ............
- 4040 of 4040 tested name servers are available
- Running initial health checks on 404 servers (35 threads): ............
- 245 of 404 tested name servers are healthy
- Making UltraDNS-2 [udns4tcam] the primary anycast - faster than UltraDNS [udns5abld] by 9.07ms
- Making OpenDNS-2 [2.lon] the primary anycast - faster than OpenDNS [2.lon] by 58.92ms
- Making DynGuide [ig-02-ams] the primary anycast - faster than DynGuide-2 [ec-02-spl] by 11.34ms
- Picking 16 secondary servers to use (8 nearest, 8 fastest)
- Waiting for wildcard cache queries from 22 servers (22 threads): 0/22............22/22
- Waiting 4s for TTL's to decrement.
- Running cache-sharing checks on 22 servers (40 threads): ............
- Disabling Localhost IPv4 [anodized] - slower replica of Internal 10-1 [anodized] by 23.5ms.
- Picking 6 secondary servers to use (3 nearest, 3 fastest)
- Benesol BE [85.158.210.68] appears to be the nearest regional (10.46ms)
- Running final health checks on 11 servers (11 threads): 0/11.......11/11

Final list of nameservers considered:
------------------------------------------------------------------------------
4.2.2.5         Genuity BAK        29  ms | 
194.74.65.68    BT-6 GB            30  ms | 
208.67.222.222  OpenDNS-2          31  ms | www.google.com is hijacked: google.navigation.opendns.com
195.99.66.220   EU BT AMS NL       34  ms | 
156.154.71.1    UltraDNS-2         41  ms | NXDOMAIN Hijacking
193.74.208.65   Scarlet-0 BE       45  ms | 
8.8.4.4         Google Public DNS- 54  ms | (excluded: Shares-cache with current primary DNS server)
8.8.8.8         Google Public DNS  57  ms | Replica of ::1, Replica of 10.0.0.1, Replica of 8.8.4.4
216.146.35.35   DynGuide           62  ms | NXDOMAIN Hijacking
82.146.118.12   Econoweb BE        63  ms | 
212.71.8.11     EDPnet-2 BE-2      66  ms | 
85.158.210.68   Benesol BE         82  ms | 

- Sending 250 queries to 11 servers: ............
- Error querying OpenDNS-2 [208.67.222.222]: www.360buy.com.: Timeout
- Error querying Econoweb BE [82.146.118.12]: tieba.baidu.com.: Timeout


Fastest individual response (in milliseconds):
----------------------------------------------
Scarlet-0 BE     ##################### 10.71286
Benesol BE       ###################### 11.12390
EDPnet-2 BE-2    ###################### 11.39688
Econoweb BE      ####################### 11.84607
OpenDNS-2        ############################ 14.16492
BT-6 GB          ############################ 14.27984
Genuity BAK      ############################ 14.33086
DynGuide         ################################# 17.08102
EU BT AMS NL     ################################### 17.74192
Google Public DN ######################################## 20.69783
UltraDNS-2       ###################################################### 27.56095

Mean response (in milliseconds):
--------------------------------
Google Public DN ########## 62.97
BT-6 GB          ################### 123.89
Scarlet-0 BE     #################### 127.88
Genuity BAK      ####################### 150.14
UltraDNS-2       ######################### 161.57
OpenDNS-2        ############################ 182.91
EU BT AMS NL     ############################# 192.26
DynGuide         ############################### 205.30
Benesol BE       ############################### 206.70
EDPnet-2 BE-2    ################################## 227.69
Econoweb BE      ##################################################### 355.61

Response Distribution Chart URL (200ms):
----------------------------------------
http://chart.apis.google.com/chart?cht=lxy&chs=720x415&chxt=x,y&chg=10,20&chxr=0,0,200|1,0,100...

Response Distribution Chart URL (Full):
---------------------------------------
http://chart.apis.google.com/chart?cht=lxy&chs=720x415&chxt=x,y&chg=10,20&chxr=0,0,3500|1,0,100...

Recommended configuration (fastest + nearest):
----------------------------------------------
nameserver 8.8.8.8         # Google Public DNS  
nameserver 193.74.208.65   # Scarlet-0 BE  
nameserver 85.158.210.68   # Benesol BE  

********************************************************************************
In this test, Your current primary DNS server is Fastest  
********************************************************************************

- Saving report to /tmp/namebench_2010-05-27_0842.html
- Saving detailed results to /tmp/namebench_2010-05-27_0842.csv


--[ FAQ ]-----------------------------------------------------------------------

See http://code.google.com/p/namebench/wiki/FAQ for more recent updates.

1) What does 'NXDOMAIN Hijacking' mean?

  This means that the specific DNS server returns a false entry when a
  non-existent record is requested. This entry likely points to a website
  serving a 'Host not found' page with banner ads.

2) What does 'www.google.com. may be hijacked' mean?

  This means that when a user requests 'www.google.com', they are being
  silently redirected to another server. The page may look like it's run by
  Google, but it is instead being proxied through another server. For details,
  try using the host command. In this case, this particular IP server is
  redirecting all traffic to http://google.navigation.opendns.com/

  % host www.google.com. 208.67.220.220
  Using domain server:
  Name: 208.67.220.220
  Address: 208.67.220.220#53
  Aliases:

  www.google.com is an alias for google.navigation.opendns.com.
  google.navigation.opendns.com has address 208.67.217.230
  google.navigation.opendns.com has address 208.67.217.231


3) What does 'google.com. may be hijacked' mean?

  The same as above, but it is a rarer condition as it breaks http://google.com/

4) What does 'thread.error: can't start new thread' mean?

  It means you are using too many threads. Try restarting namebench.py with -j8

5) What does 'unhealthy: TestWwwGoogleComResponse <class 'dns.exception.Timeout'>' mean?

  It means the specified nameserver was too slow to answer you. If all of your
  nameservers are timing out, try restarting namebench.py with -Y 4



