<#
.SYNOPSIS
  Haalt de AI-modellen op. Dit is de enige stap die internet nodig heeft.
  Zonder -Doel komen de modellen in de gedeelde map %USERPROFILE%\AI-modellen (submappen
  whisper en llm). Met -Doel komt alles in een losse map, bijvoorbeeld een USB-stick om daarna
  op meerdere laptops te installeren. Een model dat er al staat, wordt niet opnieuw opgehaald.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File modellen-ophalen.ps1 -Llm 4b
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File modellen-ophalen.ps1 -Doel D:\modellen -Llm 4b
.NOTES
  12b = groot taalmodel (ca. 7 GB), voor laptops met 16 GB werkgeheugen en een snelle processor.
  4b  = klein taalmodel (ca. 2,5 GB), aanbevolen voor Windows-laptops zonder losse videokaart.
#>
param(
  [string]$Doel = "",
  [string]$GedeeldeMap = (Join-Path $env:USERPROFILE "AI-modellen"),
  [ValidateSet("12b", "4b")][string]$Llm = "4b"
)
$ErrorActionPreference = "Stop"
$behandeld = @()

$regels = Get-Content (Join-Path $PSScriptRoot "modellen.tsv") | Where-Object { $_ -and $_ -notmatch '^#' }
foreach ($regel in $regels) {
  $sleutel, $bestand, $url = $regel -split "`t"
  if ($sleutel -ne "whisper" -and $sleutel -ne "llm-$Llm") { continue }
  if ($Doel) { $map = $Doel }
  elseif ($sleutel -eq "whisper") { $map = Join-Path $GedeeldeMap "whisper" }
  else { $map = Join-Path $GedeeldeMap "llm" }
  New-Item -ItemType Directory -Force $map | Out-Null
  $pad = Join-Path $map $bestand
  $behandeld += $pad
  if ((Test-Path $pad) -and (Get-Item $pad).Length -gt 0) {
    Write-Host "Staat er al: $bestand"
    continue
  }
  Write-Host "Ophalen: $bestand"
  $gelukt = $false
  foreach ($poging in 1..5) {     # bij een verbroken verbinding: hervatten waar we waren
    & curl.exe -L --fail --progress-bar -C - -o "$pad.deel" $url
    if ($LASTEXITCODE -eq 0) { $gelukt = $true; break }
    Write-Host "Verbinding verbroken (poging $poging van 5); de download wordt hervat..."
  }
  if (-not $gelukt) { throw "Downloaden mislukt: $url" }
  Move-Item -Force "$pad.deel" $pad
}

foreach ($pad in $behandeld | Where-Object { $_ -like "*.gguf" }) {
  $stroom = [System.IO.File]::OpenRead($pad)
  $kop = New-Object byte[] 4
  [void]$stroom.Read($kop, 0, 4)
  $stroom.Close()
  if ([System.Text.Encoding]::ASCII.GetString($kop) -ne "GGUF") { throw "Ongeldig modelbestand: $pad" }
}
Write-Host ""
Write-Host "Klaar. Modellen:"
$behandeld | ForEach-Object { Get-Item $_ } | Format-Table FullName, @{ n = "GB"; e = { [math]::Round($_.Length / 1GB, 1) } }
