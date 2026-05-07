# Start voice + interview API (Windows). Requires .env with ANTHROPIC_API_KEY for the voice service.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

if (Test-Path "$root\.env") {
  Get-Content "$root\.env" | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line -match "=") {
      $i = $line.IndexOf("=")
      $k = $line.Substring(0, $i).Trim()
      $v = $line.Substring($i + 1).Trim().Trim('"')
      Set-Item -Path "env:$k" -Value $v
    }
  }
  Write-Host "[start] Loaded $root\.env"
}

if (-not $env:ANTHROPIC_API_KEY) {
  Write-Error "ANTHROPIC_API_KEY not set. Copy .env.example to .env and set your key."
  exit 1
}

Write-Host "[start] pip install (voice + interview)..."
python -m pip install -q -r "$root\requirements.txt"

$vport = if ($env:PORT) { $env:PORT } else { "8765" }
$sport = if ($env:STATIC_PORT) { $env:STATIC_PORT } else { "8080" }
$aport = if ($env:INTERVIEW_PORT) { $env:INTERVIEW_PORT } else { "8000" }

Write-Host "[start] WebSocket (voice) :$vport  |  static :$sport  |  interview API :$aport"
Write-Host "[start] Note: full stack (postgres+redis) is easiest via docker compose."

$voice = Start-Process -FilePath "python" -ArgumentList "server.py" -WorkingDirectory $root -PassThru -WindowStyle Minimized
$static = Start-Process -FilePath "python" -ArgumentList "static_server.py" -WorkingDirectory $root -PassThru -WindowStyle Minimized
$api = Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", $aport -WorkingDirectory "$root\services\interview" -PassThru -WindowStyle Minimized
$worker = Start-Process -FilePath "python" -ArgumentList "-m", "celery", "-A", "app.worker.celery_app.celery_app", "worker", "-Q", "crm_automations", "--loglevel=info" -WorkingDirectory "$root\services\interview" -PassThru -WindowStyle Minimized

Write-Host ""
Write-Host "  Voice UI:      http://localhost:$sport"
Write-Host "  WebSocket:     ws://localhost:$vport"
Write-Host "  Interview API: http://localhost:$aport"
Write-Host "  CRM Webapp:    http://localhost:$aport/crm"
Write-Host "  API docs:      http://localhost:$aport/docs"
Write-Host "Close the minimized python windows to stop, or end those PIDs: $($voice.Id), $($static.Id), $($api.Id), $($worker.Id)"
