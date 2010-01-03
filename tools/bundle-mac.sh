#!/bin/sh
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

PKG_DIR="$HOME/Desktop"


rm -Rf $PKG_DIR/namebench.app
cp -Rp cocoa/build/Release/namebench.app $PKG_DIR/
# No longer required now that our Xcode project was setup properly.
#tmp="/tmp/namebench-$$"
#svn checkout http://namebench.googlecode.com/svn/trunk/ $tmp
#rsync -va --exclude ".svn/" --exclude "*~" --exclude "*.pyc" $tmp/ $PKG_DIR/namebench.app/Contents/Resources/
version=`grep "^VERSION" libnamebench/version.py | cut -d\' -f2`
dmg="$PKG_DIR/namebench-${version}.dmg"
if [ -f "$dmg" ]; then
  rm -f "$dmg"
fi
hdiutil create -srcfolder $PKG_DIR/namebench.app $dmg
rm -Rf $PKG_DIR/namebench.app

