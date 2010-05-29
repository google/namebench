#!/usr/bin/env python
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


"""distutils configuration: python setup.py install"""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import os
from libnamebench import version
from distutils.core import setup
try:
    import py2exe
except ImportError:
    pass

# If you don't want 3rd party libraries included, set this in your environment.  
if os.getenv('NO_THIRD_PARTY', None):
  packages=['libnamebench']
else:
  packages = [
      'libnamebench',
      'nb_third_party',
      'nb_third_party/dns',
      'nb_third_party/dns/rdtypes',
      'nb_third_party/dns/rdtypes/ANY',
      'nb_third_party/dns/rdtypes/IN',
      'nb_third_party/graphy',
      'nb_third_party/jinja2',
      'nb_third_party/httplib2',
      'nb_third_party/simplejson',
      'nb_third_party/graphy/backends',
      'nb_third_party/graphy/backends/google_chart_api'
  ]



RT_MANIFEST = 24

manifest_template = '''
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
<assemblyIdentity
    version="5.0.0.0"
    processorArchitecture="x86"
    name="%(prog)s"
    type="win32"
/>
<description>%(prog)s Program</description>
<dependency>
    <dependentAssembly>
        <assemblyIdentity
            type="win32"
            name="Microsoft.Windows.Common-Controls"
            version="6.0.0.0"
            processorArchitecture="X86"
            publicKeyToken="6595b64144ccf1df"
            language="*"
        />
    </dependentAssembly>
</dependency>
</assembly>
'''

rt90_manifest = """<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel level="asInvoker" uiAccess="false"></requestedExecutionLevel>
      </requestedPrivileges>
    </security>
  </trustInfo>
  <dependency>
    <dependentAssembly>
      <assemblyIdentity type="win32" name="Microsoft.VC90.CRT" version="9.0.21022.8" processorArchitecture="x86" publicKeyToken="1fc8b3b9a1e18e3b"></assemblyIdentity>
    </dependentAssembly>
  </dependency>
</assembly>
"""

setup(name='namebench',
      version=version.VERSION,
      py_modules=['namebench'],
      description='DNS service benchmarking tool',
      author='Thomas Stromberg',
      author_email='tstromberg@google.com',
      url='http://namebench.googlecode.com/',
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Intended Audience :: End Users/Desktop',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: Apache 2.0',
          'Operating System :: MacOS :: MacOS X',
          'Operating System :: Microsoft :: Windows',
          'Operating System :: POSIX',
          'Programming Language :: Python',
          'Topic :: Networking',
      ],
      packages=packages,
      platforms=['Any'],
      license='Apache 2.0',
      scripts=['namebench.py'],
      data_files=[
          ('namebench/config',
           ['config/namebench.cfg',
            'config/hostname_reference.cfg',
            'config/data_sources.cfg']
          ),
          ('namebench/templates',
           ['templates/ascii.tmpl',
            'templates/html.tmpl',
            'templates/resolv.conf.tmpl',
            'templates/style.css'
           ]
          ),
          ('namebench/data',
           ['data/alexa-top-2000-domains.txt',
            'data/cache-hit.txt',
            'data/cache-miss.txt',
            'data/cache-mix.txt'
           ]
          )
      ],

      # py2exe specific garbarge below.
        options={
            'py2exe': {
                'bundle_files': 3, # 1 nor 2 does not work
                'ascii': False,
                'packages': ['nb_third_party'],
                'excludes': ['dns', 'jinja2', 'graphy', 'httplib2', 'tcl', 'simplejson'],
                'dll_excludes': ["w9xpopen.exe","MSVCP90.dll", "MSVCR90.DLL"],
            }
        },
        zipfile = "namebench.zip", # None - when bundle_files 1 or 2 can work.
        windows=[{
            'script': "namebench.py",
            'dest_base': "namebench",
            'name': "namebench",
            'copyright': "(c) 2009 Google, Inc.",
            'comments': "http://namebench.googlecode.com/",
            'other_resources': [
                # Windows Common Controls, XP Look
                (RT_MANIFEST, 1, manifest_template % dict(prog="namebench")),
                # VCRT 2008
                (RT_MANIFEST, 1, rt90_manifest), # 1 - EXE CRT Manifest, 2 - DLL
            ],
        }],
#       console=['namebench.py']
)
