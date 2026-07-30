# One-command deploy to a GCP VM (or any Debian/Ubuntu server).
# Usage:  .\deploy\deploy.ps1 -ServerIp 34.12.34.56 -User myuser [-KeyPath ~\.ssh\google_compute_engine]
param(
    [Parameter(Mandatory=$true)] [string]$ServerIp,
    [Parameter(Mandatory=$true)] [string]$User,
    [string]$KeyPath = "$env:USERPROFILE\.ssh\google_compute_engine"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$tarball = Join-Path $env:TEMP "sm-automation.tar.gz"

Write-Host "== Packing project (excluding venv, secrets, runtime data) =="
if (Test-Path $tarball) { Remove-Item $tarball -Force }
tar -czf $tarball -C $projectRoot `
    --exclude "venv" --exclude "__pycache__" --exclude "*.pyc" `
    --exclude ".env" --exclude "data/.session_secret" --exclude "data/users.json" `
    --exclude "data/images" --exclude "data/published" --exclude "data/designs.json" `
    --exclude "data/sm-automation.db" --exclude "data/designs" --exclude "data/bank" `
    --exclude "mock-apis/published_posts.json" --exclude "server.log" --exclude ".claude" `
    .
if ($LASTEXITCODE -ne 0) { throw "tar failed" }
Write-Host ("   " + (Get-Item $tarball).Length / 1MB + " MB")

Write-Host "== Uploading to ${User}@${ServerIp} =="
scp -i $KeyPath $tarball "${User}@${ServerIp}:/tmp/sm-automation.tar.gz"
if ($LASTEXITCODE -ne 0) { throw "scp failed" }

Write-Host "== Running server setup =="
ssh -i $KeyPath "${User}@${ServerIp}" "tar -xzf /tmp/sm-automation.tar.gz -C /tmp ./deploy/setup-server.sh && sudo bash /tmp/deploy/setup-server.sh http://${ServerIp}"
if ($LASTEXITCODE -ne 0) { throw "remote setup failed" }

Write-Host ""
Write-Host "Done. App is live at:  http://${ServerIp}" -ForegroundColor Green
Write-Host "Mock API inspector:    http://${ServerIp}/mock/published"
