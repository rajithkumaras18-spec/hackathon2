Write-Host "Starting TruthChain..." -ForegroundColor Green
if (Test-Path "C:\Users\Adam\AppData\Local\Python\bin\python.exe") {
    & "C:\Users\Adam\AppData\Local\Python\bin\python.exe" run.py
} else {
    py run.py
}
