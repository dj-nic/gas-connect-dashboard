param([string]$Port,[switch]$Erase,[switch]$Detect,[switch]$ListPorts)
$ErrorActionPreference = 'Stop'
$runner = Join-Path $PSScriptRoot '..\scripts\flash.cmd'
$params = @()
if ($Port) { $params += @('--port',$Port) }
if ($Erase) { $params += '--erase' }
if ($Detect) { $params += '--detect' }
if ($ListPorts) { $params += '--list-ports' }
& $runner @params
if ($LASTEXITCODE -ne 0) { throw 'Flash-Assistent meldet einen Fehler.' }
