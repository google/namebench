#!/bin/sh
packages=$(grep -hr "^package" */*.go | sort -u | cut -d" " -f2 |  sed s/"^"/"\.\.\."/ | xargs)
echo "Rebuilding $packages"
go install $packages
