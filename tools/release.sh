#!/bin/sh
# Create a tarball from the subversion repository.

tmp=$$
cd /tmp
svn checkout http://namebench.googlecode.com/svn/trunk/ namebench-$$
version=`grep '^VERSION' namebench-$$/namebench.py | cut -d\' -f2`
mv namebench-$$ namebench-$version
cd namebench-$version
./namebench.py -t2 -r1
find . -name "*.pyc" -delete
cd ..
tar -zcvf namebench-${version}.tgz namebench-${version}/
rm -Rf namebench-${version}
