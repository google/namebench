PATH=C:\python26;C:\progra~2\7-zip;%PATH%
del /q /s dist\*.*
python setup.py py2exe
cd dist
7z d library.zip jinja2\* dns\* 'graphy\*
del /s w9xpopen.exe
copy ..\README.txt .
7z a namebench_for_Windows.zip -r *
namebench -x -O 8.8.8.8 -t5 -o test.html
start test.html

cd ..
