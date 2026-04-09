@echo on

rem - this is  a sample build script for building gui_tool MSI file under windows, it assumes the following:
rem - you already have a python.org python installed (at least 3.10) tested on 3.10.2
rem - you have a git checkout of [the correct] gui_tool [release] here

rem - how to use:
rem - step 1 - edit the script to change the PATH below to include your python 3.10 install directory
rem - step 2 - open a command prompt
rem - step 3 - run winbuild_venv.bat in the gui_tool directory

rem NOTE: you need visual studio installed, with the C++ build tools

rem Use the virtual environment Python instead of system Python for compatibility
SET VENV_PYTHON=C:\Users\bluea\OneDrive\Documents\GitHub\gui_tool\.venv\Scripts\python.exe

%VENV_PYTHON% --version

%VENV_PYTHON% -m pip install -U cx_Freeze
%VENV_PYTHON% -m pip install -U pymavlink
%VENV_PYTHON% -m pip install -U pywin32
%VENV_PYTHON% -m pip install -U python-can
%VENV_PYTHON% -m pip install -U .

rem show pip sizes for debug
%VENV_PYTHON% pip_sizes.py

rem  make the .msi
%VENV_PYTHON% setup.py install
%VENV_PYTHON% setup.py bdist_msi

rem find the binary in 'dist' folder
dir dist