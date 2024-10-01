namebench 2.0
=============
namebench provides personalized DNS server recommendations based on your
browsing history.

WARNING: This tool is in the midst of a major rewrite. The "master" branch is currently in experimental
form and currently lacks a user interface, nor does it support any command-line options.

For stable binaries, please see https://code.google.com/p/namebench/

What can one expect in namebench 2.0?

* Faster
* Simpler interface
* More comprehensive results
* CDN benchmarking
* DNSSEC support


BUILDING:
=========
Building requires Go 1.23.1 to be installed: http://golang.org/

* Create a workspace directory, and cd into it.
* Prepare your workspace directory:

```shell
    go get
```

* Build it.

```shell
    go build namebench
```

You should have an executable named 'namebench' in the current directory.


RUNNING:
========
* CLI mode: (go run) namebench --mode now --join_string '\t' --dns_filter 0

* End-user: run ./namebench, which should open up a UI window.
* Developer, run ./namebench_dev_server.sh for an auto-reloading webserver at http://localhost:9080/
