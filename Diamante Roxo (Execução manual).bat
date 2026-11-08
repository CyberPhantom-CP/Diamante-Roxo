@echo off
cd /d "%~dp0Script"
"C:\Program Files\PowerShell\7\pwsh.exe" -NoProfile -Command "python '%~dp0Script\Diamante Roxo.py'"
pause
