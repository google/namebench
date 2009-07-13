=======
itty.py
=======

The itty-bitty Python web framework.

``itty.py`` is a little experiment, an attempt at a Sinatra_ influenced 
micro-framework that does just enough to be useful and nothing more.

Currently supports:

* Routing
* Basic responses
* Content-types
* HTTP Status codes
* URL Parameters
* Basic GET/POST/PUT/DELETE support
* User-definable error handlers
* Redirect support
* File uploads
* Header support
* Static media serving

Beware! If you're looking for a proven, enterprise-ready framework, you're in
the wrong place. But it sure is a lot of fun.

.. _Sinatra: http://sinatrarb.com/


Example
=======

::

  from itty import get, run_itty
  
  @get('/')
  def index(request):
      return 'Hello World!'
  
  run_itty()

See ``examples/`` for more usages.


Other Sources
=============

A couple of bits have been borrowed from other sources:

* Django

  * HTTP_MAPPINGS

* Armin Ronacher's blog (http://lucumr.pocoo.org/2007/5/21/getting-started-with-wsgi)

  * How to get started with WSGI


Thanks
======

Thanks go out to Matt Croydon & Christian Metts for putting me up to this late
at night. The joking around has become reality. :)