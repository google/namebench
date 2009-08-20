#!/bin/sh
# Create a tarball from the subversion repository.

tmp=$$
cd /tmp
svn checkout http://namebench.googlecode.com/svn/trunk/ namebench-$$
version=`grep '^VERSION' namebench-$$/namebench.py | cut -d\' -f2`
mv namebench-$$ namebench-$version
cd namebench-$version
./namebench.py -t2 -r1 -j40 -o /tmp/$$.csv 208.67.220.220
find . -name "*.pyc" -delete
find . -name ".svn" -exec rm -Rf {} \; 2>/dev/null
cd ..
tar -zcvf namebench-${version}.tgz namebench-${version}/
rm -Rf namebench-${version}
