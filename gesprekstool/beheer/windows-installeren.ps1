#Requires -RunAsAdministrator
<#
.SYNOPSIS
  Installeert de Gesprekstool voor alle gebruikers van deze computer:
  programma, modellen, firewallregel (netwerkblokkade) en snelkoppeling in het startmenu.
.DESCRIPTION
  De app zoekt elk model eerst in de gedeelde map (standaard %USERPROFILE%\AI-modellen, met de
  submappen whisper en llm) en daarna op de oude plek %ProgramData%\Gesprekstool\models.
  Voor elk model in -Modellen geldt:
    - staat het al in de gedeelde map of op de oude plek: er wordt niets gekopieerd;
    - staat het nog nergens: het komt in de gedeelde map;
    - heeft het een andere naam dan de standaardmodellen (modellen.tsv): het gaat, zoals
      voorheen, naar de oude plek.
  Er worden nooit modelbestanden verwijderd, ook niet bij -Verwijderen buiten de oude plek.
  -GedeeldeMap kiest een andere gedeelde map (bijvoorbeeld C:\Users\Public\AI-modellen op een
  laptop met meerdere gebruikers) en legt die vast in %ProgramData%\Gesprekstool\config.json.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File windows-installeren.ps1 -Modellen D:\modellen
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File windows-installeren.ps1 -Modellen D:\modellen -GedeeldeMap C:\Users\Public\AI-modellen
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File windows-installeren.ps1 -Verwijderen
#>
param(
  [string]$Modellen = "",
  [string]$GedeeldeMap = "",
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
  Write-Host "Niet aangeraakt: de gedeelde modelmap (AI-modellen) en de gesprekken in %LOCALAPPDATA%\Gesprekstool."
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

$expliciet = [bool]$GedeeldeMap
if (-not $GedeeldeMap) { $GedeeldeMap = Join-Path $env:USERPROFILE "AI-modellen" }
Write-Host "2/4 Modellen (gedeelde map: $GedeeldeMap)"
$oud = Join-Path $systeem "models"
New-Item -ItemType Directory -Force $systeem | Out-Null
if ($expliciet) {
  $config = Join-Path $systeem "config.json"
  $instellingen = New-Object PSObject
  if (Test-Path $config) { $instellingen = Get-Content -Raw $config | ConvertFrom-Json }
  $instellingen | Add-Member -NotePropertyName gedeelde_modellen_map -NotePropertyValue $GedeeldeMap -Force
  $instellingen | ConvertTo-Json | Set-Content -Encoding UTF8 $config
  Write-Host "   Gedeelde map vastgelegd in $config"
}
$standaard = Get-Content (Join-Path $PSScriptRoot "modellen.tsv") |
  Where-Object { $_ -and $_ -notmatch '^#' } | ForEach-Object { ($_ -split "`t")[1] }
if ($Modellen) {
  $bestanden = Get-ChildItem -Path $Modellen -Recurse -Depth 1 -File |
    Where-Object { $_.Name -like "ggml-*.bin" -or $_.Name -like "*.gguf" }
  foreach ($bestand in $bestanden) {
    $soort = if ($bestand.Name -like "ggml-*.bin") { "whisper" } else { "llm" }
    if ($standaard -notcontains $bestand.Name) {
      Write-Host "   $($bestand.Name): geen standaardmodel, naar $oud"
      New-Item -ItemType Directory -Force $oud | Out-Null
      Copy-Item -Force $bestand.FullName $oud
    } elseif (Test-Path (Join-Path (Join-Path $GedeeldeMap $soort) $bestand.Name)) {
      Write-Host "   $($bestand.Name): staat al in de gedeelde map, niet gekopieerd"
    } elseif (Test-Path (Join-Path $oud $bestand.Name)) {
      Write-Host "   $($bestand.Name): staat al op de oude plek ($oud), niet gekopieerd"
    } else {
      $map = Join-Path $GedeeldeMap $soort
      Write-Host "   $($bestand.Name): naar $map"
      New-Item -ItemType Directory -Force $map | Out-Null
      Copy-Item -Force $bestand.FullName (Join-Path $map "$($bestand.Name).deel")
      Move-Item -Force (Join-Path $map "$($bestand.Name).deel") (Join-Path $map $bestand.Name)
    }
  }
} else {
  Write-Host "   Geen map met modellen opgegeven: er wordt niets gekopieerd."
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
