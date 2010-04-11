from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from django.utils import simplejson

class IndexHost(db.Model):
  record_type = db.StringProperty()
  record_name = db.StringProperty()
  listed = db.BooleanProperty()

hosts = [
    ('A', 'www.google.com.'),
    ('A', 'reddit.com.'),
    ('A', 'www.baidu.com.'),
    ('A', 'www.google.com.'),
    ('A', 'www.microsoft.com.'),
    ('A', 'www.facebook.com.'),
    ('A', 'www.youtube.com.')
]

for h_type, h_name in hosts:
  entry = IndexHost()
  entry.record_type = h_type
  entry.record_name = h_name
  entry.listed = True
  entry.put()
