$record=Join-Path $PSScriptRoot 'data/processes.json'
if (Test-Path -LiteralPath $record) {
 foreach($entry in @(Get-Content -LiteralPath $record | ConvertFrom-Json)) {
  $proc=Get-Process -Id $entry.id -ErrorAction SilentlyContinue
  if($proc -and $proc.StartTime.ToUniversalTime() -eq ([datetime]$entry.start).ToUniversalTime()){Stop-Process -Id $proc.Id}
 }
 Remove-Item -LiteralPath $record
}
Write-Output 'Stopped only the processes recorded by start-local.ps1.'
