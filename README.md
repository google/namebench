namebench 2.0
=============
namebench provides personalized DNS server recommendations based on your
browsing history.

WARNING: This tool is in the midst of a major rewrite. The master branch is
unlikely to even compile as of early October, 2013. For stable binaries,
please see https://code.google.com/p/namebench/

What can one expect in namebench 2.0?

* Faster
* Simpler interface
* More comprehensive results
* CDN benchmarking


BUILDING:
=========
Collect your dependencies:

export GOPATH=`pwd`
go get github.com/mattn/go-sqlite3
go get code.google.com/p/go.net/publicsuffix
go build namebench

