#!/bin/bash
# poor mans multi-platform restart for the dev server.
# requires: watchdog 0.6.0

killall namebench
./build.sh && go run namebench.go --port 9080 &

watchmedo shell-command \
  --patterns="*.go;*.html;*.css;*.tmpl" \
  --ignore-directories \
  --recursive \
  --command='killall namebench; ./build.sh; go run namebench.go --port 9080' \
  .
