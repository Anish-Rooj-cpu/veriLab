@echo off
echo Building Verilog Studio...
python -m PyInstaller -y --name "Verilog Studio" --windowed --noconsole main.py
echo Build Complete! Check the 'dist' folder.
pause
