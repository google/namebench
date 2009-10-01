#!/bin/sh
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
#
#
#
# This script is provided to update the data/top-10000.txt file.

CSV='top-1m.csv'

# TODO(tstromberg): Replace this bad hack. In real-world observations, hosts
# only use 1-2 Google TLD's. Clean all but the real one to match reality.
REMOVE='google\.[a-z][a-z]$|google\.co\.|google\.com\.[a-z][a-z]'
ALEXA_URL=http://s3.amazonaws.com/alexa-static/$CSV.zip
TOP_COUNT=10000
UNIQ_COUNT=14000
OUTPUT=alexa-top-${TOP_COUNT}-global.txt

if [ ! -f "$CSV" ]; then
  if [ ! -f "${CSV}.zip" ]; then
    echo "${CSV}.zip not found - Fetching $ALEXA_URL"
    curl -O $ALEXA_URL
  fi
  unzip -o $CSV.zip $CSV
fi

rm $OUTPUT
cut -d, -f2 $CSV | cut -d/ -f1 | head -$UNIQ_COUNT | ./ordered-uniq.py | \
  egrep -v $REMOVE | head -$TOP_COUNT > $OUTPUT
ls -la $OUTPUT



