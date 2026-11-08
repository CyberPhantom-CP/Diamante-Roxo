#Requires -Version 7.0
# Atalho manual via PWS7 — dispara a task agendada "Diamante Roxo"
# Equivalente ao .bat, mas rodando 100% no PowerShell 7 (sem passar pelo CMD)
$TaskName = "Diamante Roxo"

# Garante Bypass na sessao (sem isso o .ps1 de dupla execucao nao dispara)
try { Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force -ErrorAction SilentlyContinue } catch {}

try {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    if ($task.State -eq "Running") {
        Write-Host "Task '$TaskName' ja em execucao — ignorado." -ForegroundColor Yellow
    } else {
        Start-ScheduledTask -TaskName $TaskName
        Start-Sleep -Seconds 2
        $nova = Get-ScheduledTask -TaskName $TaskName
        if ($nova.State -eq "Running") {
            Write-Host "Task '$TaskName' disparada! Olha a janela pwsh visivel." -ForegroundColor Green
        } else {
            Write-Host "Task '$TaskName' disparada (Estado: $($nova.State))." -ForegroundColor Green
        }
    }
} catch {
    Write-Host "ERRO: Falha ao disparar a task '$TaskName': $_" -ForegroundColor Red
    exit 1
}
