param(
 [string]$Python = '',
 [string]$Ollama = '',
 [string]$Models = '',
 [switch]$Mobile,
 [string]$MobileToken = ''
)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$bundledOllama = Join-Path $PSScriptRoot 'runtime/ollama/ollama.exe'
$bundledModels = Join-Path $PSScriptRoot 'runtime/ollama-models'
if (!$Python) { $Python = (Get-Command python.exe -ErrorAction Stop).Source }
if (!$Ollama) {
 if (Test-Path -LiteralPath $bundledOllama) { $Ollama = $bundledOllama }
 else { $Ollama = (Get-Command ollama.exe -ErrorAction Stop).Source }
}
if (!$Models -and (Test-Path -LiteralPath $bundledModels)) { $Models = $bundledModels }
New-Item -ItemType Directory -Force -Path "$PSScriptRoot/data" | Out-Null
if (!(Test-Path -LiteralPath "$PSScriptRoot/data/bus.db")) { throw 'Import the authorised workbook first. See README.md.' }
$started=@()
function PortUsed($port) { return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) }
if (!(PortUsed 11434)) {
 if ($Models) { $env:OLLAMA_MODELS=(Resolve-Path -LiteralPath $Models).Path }
 $env:OLLAMA_HOST='127.0.0.1:11434'
 $env:OLLAMA_CONTEXT_LENGTH='8192'
 $proc=Start-Process -FilePath $Ollama -ArgumentList 'serve' -WindowStyle Hidden -PassThru -RedirectStandardOutput "$PSScriptRoot/data/model.out.log" -RedirectStandardError "$PSScriptRoot/data/model.err.log"
 $started+=@{id=$proc.Id;start=$proc.StartTime.ToUniversalTime().ToString('o')}
}
if ($Mobile) {
 $tokenPath = Join-Path $PSScriptRoot 'data/mobile-api-token.txt'
 if (!$MobileToken -and (Test-Path -LiteralPath $tokenPath)) { $MobileToken = (Get-Content -LiteralPath $tokenPath -Raw).Trim() }
 if (!$MobileToken) {
  $bytes = New-Object byte[] 32
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
  $MobileToken = ([System.BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
  Set-Content -LiteralPath $tokenPath -Value $MobileToken -NoNewline
 }
 if ($MobileToken.Length -lt 32) { throw 'Mobile API token must contain at least 32 characters.' }
 $env:BUSWISE_HOST='0.0.0.0'
 $env:BUSWISE_MOBILE_TOKEN=$MobileToken
 Write-Output 'Mobile API pairing is enabled. Copy data/mobile-api-token.txt into Android local.properties as BUSWISE_MOBILE_TOKEN before running the app.'
}
if (!(PortUsed 8765)) {
 $proc=Start-Process -FilePath $Python -ArgumentList 'backend/server.py' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput "$PSScriptRoot/data/api.out.log" -RedirectStandardError "$PSScriptRoot/data/api.err.log"
 $started+=@{id=$proc.Id;start=$proc.StartTime.ToUniversalTime().ToString('o')}
}
if (!(PortUsed 3000)) {
 $node=(Get-Command node.exe).Source
 $proc=Start-Process -FilePath $node -ArgumentList 'node_modules/vinext/dist/cli.js dev' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput "$PSScriptRoot/data/web.out.log" -RedirectStandardError "$PSScriptRoot/data/web.err.log"
 $started+=@{id=$proc.Id;start=$proc.StartTime.ToUniversalTime().ToString('o')}
}
if ($started.Count -gt 0) {
 $old=@();if (Test-Path -LiteralPath "$PSScriptRoot/data/processes.json") {$old=@(Get-Content -LiteralPath "$PSScriptRoot/data/processes.json" | ConvertFrom-Json)}
 ConvertTo-Json -InputObject @($old+$started) | Set-Content -LiteralPath "$PSScriptRoot/data/processes.json"
}
Write-Output 'Buswise started. Open http://127.0.0.1:3000 after a few seconds.'



