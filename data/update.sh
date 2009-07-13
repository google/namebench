#!/bin/sh
ALEXA_URL=http://s3.amazonaws.com/alexa-static/top-1m.csv.zip
TOP_COUNT=10000
OUTPUT=top-${TOP_COUNT}.txt

echo "Fetching $ALEXA_URL"
curl -O $ALEXA_URL
unzip -o top-1m.csv.zip top-1m.csv
head -$TOP_COUNT top-1m.csv | cut -d, -f2 | cut -d/ -f1 > $OUTPUT
rm -f top-1m.csv*
ls -la $OUTPUT



