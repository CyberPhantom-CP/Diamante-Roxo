#Requires -Version 7.0
# Manutencao automatica do Diamante Roxo (mensal, 3h) - ordem segura: SFC -> DISM Cleanup -> Optimize -> CHKDSK leitura
$log = "C:\Users\eduar\AppData\Local\Temp\opencode\manutencao_log.txt"
"=== MANUTENCAO $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Out-File $log -Append -Encoding utf8
try { Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force -ErrorAction SilentlyContinue } catch {}
$sfc = & "C:\Windows\System32\sfc.exe" /scannow 2>&1 | Out-String -Width 200
$sfc | Out-File $log -Append -Encoding utf8
if ($sfc -match "não encontrou nenhuma|did not find any|no integrity") {
  Write-Output "SFC OK - sem violacao, pulando RestoreHealth." | Out-File $log -Append -Encoding utf8
} else {
  Write-Output "SFC achou problema - rodando DISM RestoreHealth + SFC de novo..." | Out-File $log -Append -Encoding utf8
  & "C:\Windows\System32\DISM.exe" /Online /Cleanup-Image /RestoreHealth 2>&1 | Out-String -Width 200 | Out-File $log -Append -Encoding utf8
  & "C:\Windows\System32\sfc.exe" /scannow 2>&1 | Out-String -Width 200 | Out-File $log -Append -Encoding utf8
}
& "C:\Windows\System32\DISM.exe" /Online /Cleanup-Image /StartComponentCleanup 2>&1 | Out-String -Width 200 | Out-File $log -Append -Encoding utf8
try { Optimize-Volume -DriveLetter C -ReTrim | Out-Null; Write-Output "ReTrim C OK" | Out-File $log -Append -Encoding utf8 } catch { Write-Output "ReTrim C FALHOU: $_" | Out-File $log -Append -Encoding utf8 }
try { Optimize-Volume -DriveLetter D -Analyze | Out-Null; Optimize-Volume -DriveLetter D -Defrag | Out-Null; Write-Output "Defrag D OK" | Out-File $log -Append -Encoding utf8 } catch { Write-Output "Defrag D FALHOU: $_" | Out-File $log -Append -Encoding utf8 }
& "C:\Windows\System32\chkdsk.exe" C: 2>&1 | Out-String -Width 200 | Out-File $log -Append -Encoding utf8
& "C:\Windows\System32\chkdsk.exe" D: 2>&1 | Out-String -Width 200 | Out-File $log -Append -Encoding utf8
Write-Output "FIM $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File $log -Append -Encoding utf8
