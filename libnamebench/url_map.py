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

"""Create URL's for a given set of text."""


NOTE_MAP = {
    'NXDOMAIN': 'http://code.google.com/p/namebench/wiki/FAQ#What_does_"NXDOMAIN_hijacking"_mean?',
    'cache poisoning': 'http://www.kb.cert.org/vuls/id/800113',
    'Vulnerable to poisoning attacks': 'http://www.kb.cert.org/vuls/id/800113',
    'Wrong result': 'http://code.google.com/p/namebench/wiki/FAQ#What_does_"Incorrect_result_for..."_mean?',
    'is hijacked': 'http://code.google.com/p/namebench/wiki/FAQ#What_does_"Incorrect_result_for..."_mean?',
    'appears incorrect': 'http://code.google.com/p/namebench/wiki/FAQ#What_does_"Incorrect_result_for..."_mean?',
}


def GetUrlForNote(note):
  if not note:
    return None
  if not isinstance(note, str):
    print "Odd: Got a non-string note: %s (%s)" % (note, type(note))
    return None
  url = None
  for keyword in NOTE_MAP:
    if keyword in note:
      url = NOTE_MAP[keyword]
  return url


def CreateNoteUrlTuples(notes):
  note_tuples = []
  for note in notes:
    note_tuples.append({'text': note, 'url': GetUrlForNote(note)})
  return note_tuples


