PATH=C:\python26;C:\progra~1\7-zip;C:\progra~2\7-zip;%PATH%
rmdir /q /s dist\*.*
del /s /q dist\*.*
python setup.py py2exe
cd dist
#7z d namebench.zip jinja2\* dns\* 'graphy\*
7z d namebench.zip tcl\*.*
rmdir /s /q tcl\tcl8.5\tzdata tcl\tk8.5\demos
del tcl\tk8.5\images\*.eps
copy ..\README.txt .
7z a namebench_for_Windows.zip -r * >nul
namebench -x -O 8.8.8.8 -t5 -o test.html
start test.html

cd ..
