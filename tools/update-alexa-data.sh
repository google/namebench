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

ALEXA_URL=http://s3.amazonaws.com/alexa-static/top-1m.csv.zip
TOP_COUNT=10000
OUTPUT=top-${TOP_COUNT}.txt

echo "Fetching $ALEXA_URL"
curl -O $ALEXA_URL
unzip -o top-1m.csv.zip top-1m.csv
head -$TOP_COUNT top-1m.csv | cut -d, -f2 | cut -d/ -f1 > $OUTPUT
rm -f top-1m.csv*
ls -la $OUTPUT



