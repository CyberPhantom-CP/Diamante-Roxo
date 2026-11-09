#Requires -Version 7.0
# Atalho manual via PWS7 — dispara a task agendada "Diamante Roxo" (invisível, como o .bat)
try { Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force -ErrorAction SilentlyContinue } catch {}
Start-ScheduledTask -TaskName "Diamante Roxo"
