@echo off
echo Building Verilog Studio...
python -m PyInstaller -y --name "Verilog Studio" --windowed --noconsole --icon=icon.ico --add-data "icon.png;." main.py
echo Build Complete! Check the 'dist' folder.
pause
