# Stop **Python** dev processes bound to voice + interview ports (Windows).
# Only targets ProcessName "python" so Docker/WSL are not killed on shared ports.
# Run:  powershell -ExecutionPolicy Bypass -File .\scripts\stop_dev.ps1
$ports = @(8080, 8765, 8000)
foreach ($p in $ports) {
  $conns = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
  foreach ($c in $conns) {
    $processId = $c.OwningProcess
    try {
      $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
      if (-not $proc -or $proc.ProcessName -notin @("python", "pythonw")) {
        continue
      }
      Stop-Process -Id $processId -Force -ErrorAction Stop
      Write-Host "Stopped PID $processId ($($proc.ProcessName)) on port $p"
    } catch {
      Write-Warning "Could not stop PID $processId on port $p : $_"
    }
  }
}
Write-Host "Done. Start again with:  .\scripts\start_dev.ps1"
