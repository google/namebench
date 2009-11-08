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


from namebench import VERSION
from distutils.core import setup
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
      packages=['libnamebench'],
      platforms=['Any'],
      requires=['graphy', 'dnspython', 'jinja2'],
      license='Apache 2.0',
      scripts=['namebench.py'],      
      data_files=[
          ('namebench', ['namebench.cfg']),
          ('namebench/data', ['data/alexa-top-10000-global.txt'])
      ]
)
