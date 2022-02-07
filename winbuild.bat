@echo on

rem - what is this?
rem - this is  a sample build script for building gui_tool .exe file under windows, it assumes the following:
rem - you already have a Winpython 3.9 install here: Desktop\WPy64-3980\
rem - you have a git checkout of [the correct] gui_tool [release] here:   Desktop\gui_tool\

rem - how to use: 
rem - step 1 - in windows, navigate to your Desktop\WPy64-3980\ in explorer.exe and run "WinPython Command Prompt.exe" to open a 'dos box' with the correct python environment already setup.
rem - step 2 - in the new 'dos box',  typing 'python' an/or 'pip' should work and give u the correct version. ( 3.9.x )
rem - step 3 - cd to your Desktop\gui_tool\ folder :  " cd ..\..\gui_tool "
rem - step 4 - run this script:    "winbuild.bat"
rem - step 5 - go get a coffee, as it will take ages. then eventually it will be done. look in 'dist' folder.

rem  You can get the winpython installer from  https://github.com/winpython/winpython/releases .
rem     get the large '64' file  Winpython64-3.9.8.0.exe => 788MB
rem    ( as it has Qt and more other stuff included for us )
rem     https://github.com/winpython/winpython/releases/download/4.6.20211106/Winpython64-3.9.8.0.exe

rem heres some commands that might help u with the above prerequsites.
rem cd C:\Users\%USERNAME%\Desktop
rem powershell -Command "Invoke-WebRequest https://github.com/winpython/winpython/releases/download/4.6.20211106/Winpython64-3.9.8.0.exe -OutFile Winpython64-3.9.8.0.exe"
rem Winpython64-3.9.8.0.exe -y -gm2


echo %USERNAME%
dir


cd C:\Users\%USERNAME%\Desktop

echo C:\Users\%USERNAME%\Desktop\WPy64-3980\
dir C:\Users\%USERNAME%\Desktop\WPy64-3980
SET PATH=C:\Users\%USERNAME%\Desktop\WPy64-3980\python-3.9.8.amd64;%PATH%
python --version

call C:\Users\%USERNAME%\Desktop\WPy64-3980\scripts\env.bat
python --version

cd C:\Users\%USERNAME%\Desktop\gui_tool

dir
pip --version
echo "LIST1"
pip list

rem  need at least 6.6:, this gets us 6.8.2  https://github.com/marcelotduarte/cx_Freeze/discussions/949
pip install --upgrade cx_Freeze

rem remove pydronecan pip as its probably due for an update..
pip uninstall -y dronecan
pip install -U dronecan

pip uninstall -y pymavlink
pip install -U pymavlink

python pip_sizes.py

echo "LIST2"
pip list

rem  put back just the needed as found in setup.py's list :
pip install .

echo "LIST3"
pip list
python pip_sizes.py

rem  finally make the .msi
python setup.py install
python setup.py bdist_msi

rem find the binary in 'dist' folder
dir dist
