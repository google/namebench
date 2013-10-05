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

"""Mocks for tests."""

__author__ = 'tstromberg@google.com (Thomas Stromberg)'

import time
import nameserver

# external dependencies (from third_party)
import dns.message
import dns.rdataclass
import dns.query

GOOD_IP = '127.0.0.1'
SLOW_IP = '9.9.9.9'
PERFECT_IP = '127.127.127.127'
NO_RESPONSE_IP = '10.0.0.1'
BROKEN_IP = '192.168.0.1'

class MockNameServer(nameserver.NameServer):
  """Act like Nameserver, but do not issue any actual queries!"""

  def FakeAnswer(self, request, no_answer=False):
    if not request:
      request = self.CreateRequest('www.com', 'A', dns.rdataclass.IN)

    response_text = """id 999
opcode QUERY
rcode NOERROR
flags QR RD RA
;QUESTION
www.paypal.com. IN A
;ANSWER
www.paypal.com. 159 IN A 66.211.169.65
www.paypal.com. 159 IN A 66.211.169.2
;AUTHORITY
paypal.com. 3459 IN NS ppns1.den.paypal.com.
paypal.com. 3459 IN NS ppns1.phx.paypal.com.
paypal.com. 3459 IN NS ppns2.den.paypal.com.
paypal.com. 3459 IN NS ppns2.phx.paypal.com.
;ADDITIONAL
ppns1.den.paypal.com. 165480 IN A 216.113.188.121
ppns1.phx.paypal.com. 73170 IN A 66.211.168.226
ppns2.den.paypal.com. 73170 IN A 216.113.188.122
ppns2.phx.paypal.com. 73170 IN A 66.211.168.227"""
    msg = dns.message.from_text(response_text)
    msg.question = request.question
    if no_answer:
      msg.answer = None
    return msg

  def Query(self, request, timeout):
    """Return a falsified DNS response."""
    question = str(request.question[0])
    if self.ip == BROKEN_IP:
      raise dns.query.BadResponse('This sucks.')

    if self.ip == NO_RESPONSE_IP:
      answer = self.FakeAnswer(request, no_answer=True)
    elif self.ip == GOOD_IP and  'www.google.com' in question:
      answer = self.FakeAnswer(request, no_answer=True)
    else:
      answer = self.FakeAnswer(request)

    if self.ip == GOOD_IP:
      time.sleep(0.001)
    elif self.ip == SLOW_IP:
      time.sleep(0.03)
    return answer
