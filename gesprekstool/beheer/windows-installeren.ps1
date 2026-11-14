#Requires -RunAsAdministrator
<#
.SYNOPSIS
  Installeert de Gesprekstool voor alle gebruikers van deze computer:
  programma, modellen, firewallregel (netwerkblokkade) en snelkoppeling in het startmenu.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File windows-installeren.ps1 -Modellen D:\modellen
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File windows-installeren.ps1 -Verwijderen
#>
param(
  [string]$Modellen = "",
  [string]$Doel = (Join-Path $env:ProgramFiles "Gesprekstool"),
  [switch]$Verwijderen
)
$ErrorActionPreference = "Stop"
$regel = "Gesprekstool netwerkblokkade"      # zelfde naam als in gesprekstool/kern.py
$systeem = Join-Path $env:ProgramData "Gesprekstool"
$snelkoppeling = Join-Path $env:ProgramData "Microsoft\Windows\Start Menu\Programs\Gesprekstool.lnk"
$bron = Split-Path -Parent $PSScriptRoot      # de pakketmap met Gesprekstool.exe

& netsh advfirewall firewall delete rule name="$regel" | Out-Null

if ($Verwijderen) {
  foreach ($pad in $Doel, $systeem, $snelkoppeling) {
    if (Test-Path $pad) { Remove-Item -Recurse -Force $pad }
  }
  Write-Host "De Gesprekstool is verwijderd."
  Write-Host "Gesprekken van gebruikers staan nog in hun eigen map: %LOCALAPPDATA%\Gesprekstool"
  return
}

if (-not (Test-Path (Join-Path $bron "Gesprekstool.exe"))) {
  throw "Gesprekstool.exe niet gevonden in $bron. Start dit script vanuit de map 'beheer' van het pakket."
}

Write-Host "1/4 Programma kopieren naar $Doel"
if ((Resolve-Path $bron).Path.TrimEnd('\') -ne $Doel.TrimEnd('\')) {
  if (Test-Path $Doel) { Remove-Item -Recurse -Force $Doel }
  Copy-Item -Recurse -Force $bron $Doel
}

Write-Host "2/4 Modellen plaatsen in $systeem\models"
New-Item -ItemType Directory -Force (Join-Path $systeem "models") | Out-Null
if ($Modellen) {
  Copy-Item -Force (Join-Path $Modellen "*") (Join-Path $systeem "models")
}

Write-Host "3/4 Netwerkblokkade instellen (Windows Firewall)"
foreach ($exe in Get-ChildItem -Path $Doel -Recurse -Filter *.exe) {
  foreach ($richting in "out", "in") {
    & netsh advfirewall firewall add rule name="$regel" dir=$richting action=block `
      program="$($exe.FullName)" enable=yes profile=any | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Firewallregel toevoegen mislukt voor $($exe.Name)" }
  }
}

Write-Host "4/4 Snelkoppeling in het startmenu"
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($snelkoppeling)
$lnk.TargetPath = Join-Path $Doel "Gesprekstool.exe"
$lnk.WorkingDirectory = $Doel
$lnk.Description = "Gesprekken offline opnemen en samenvatten"
$lnk.Save()

Write-Host ""
Write-Host "Controle:"
& (Join-Path $Doel "gesprekstool-cli.exe") --controle
exit 0
