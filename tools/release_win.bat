rem Tool to assemble Windows builds
rem Requirements are 7-zip, py2exe, and FreeExtractor

PATH=C:\python27;C:\python26;C:\progra~1\7-zip;C:\progra~2\7-zip;%PATH%

rem ****** Clean out the old junk
del /s /f /q dist

rem ****** Compile our executable and core zipfile
python setup.py py2exe

rem ****** Remove extras from core zipfile
cd dist
7z d namebench.zip tcl\*.*
rmdir /s /q tcl\tcl8.5\tzdata tcl\tk8.5\demos
del tcl\tk8.5\images\*.eps

rem ****** Final assembly of zipfile
copy ..\README.txt .
7z a namebench_for_Windows.zip -r * >nul

rem ****** Test assembled zipfile
namebench -x -O 8.8.8.8 -q5 -o test.html
start test.html

cd ..
