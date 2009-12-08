#!/usr/bin/env python
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

"""Like uniq, but does not require sort-order to change."""

import sys
seen = {}
for full_line in sys.stdin:
  line = full_line.rstrip()
  if line not in seen:
    sys.stdout.write(full_line)
    seen[line] = 1

sys.stdout.close()
sys.stdin.close()
