@echo off
echo Starting TruthChain...
if exist "C:\Users\Adam\AppData\Local\Python\bin\python.exe" (
    "C:\Users\Adam\AppData\Local\Python\bin\python.exe" run.py
) else (
    py run.py
)
pause
