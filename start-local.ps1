param(
 [string]$Python = '',
 [string]$Ollama = '',
 [string]$Models = ''
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
Write-Output 'Buswise: http://127.0.0.1:3000 (allow a few seconds for startup). Existing services were left running.'
