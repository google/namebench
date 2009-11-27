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
from namebench import VERSION
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
      'third_party',
      'third_party/dns',
      'third_party/dns/rdtypes',
      'third_party/dns/rdtypes/ANY',
      'third_party/dns/rdtypes/IN',
      'third_party/graphy',
      'third_party/jinja2',
      'third_party/graphy/backends',
      'third_party/graphy/backends/google_chart_api'
  ]



setup(name='namebench',
      version=VERSION,
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
          ('namebench', ['namebench.cfg']),
          ('namebench/templates',
           ['templates/ascii.tmpl',
                'templates/html.tmpl',
                'templates/style.css'
           ]
          ),
          ('namebench/data', ['data/alexa-top-10000-global.txt'])
      ],
      
      # py2exe specific garbarge below.
      options={
        'py2exe': {
            # This gets.. weird.
            'packages': ['third_party'],
            'ignores': ['dns', 'jinja2', 'graphy'],
        }
      },
      windows=['namebench.py'],
)
