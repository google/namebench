#!/bin/sh
PKG_DIR="$HOME/Desktop"

rm -Rf $PKG_DIR/namebench.app
cp -Rp cocoa/build/Debug/namebench.app $PKG_DIR/
rsync -va --exclude ".svn/" --exclude "*~" --exclude "*.pyc" . $PKG_DIR/namebench.app/Contents/Resources/
#open $PKG_DIR/namebench.app
version=`grep "^VERSION" namebench.py | cut -d\' -f2`
hdiutil create -srcfolder $PKG_DIR/namebench.app $PKG_DIR/namebench-${version}.dmg

