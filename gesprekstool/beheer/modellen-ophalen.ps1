<#
.SYNOPSIS
  Haalt de AI-modellen op. Dit is de enige stap die internet nodig heeft.
  Doe dit een keer op een beheercomputer en kopieer de map daarna naar de laptops.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File modellen-ophalen.ps1 -Doel D:\modellen -Llm 4b
.NOTES
  12b = groot taalmodel (ca. 7 GB), voor laptops met 16 GB werkgeheugen en een snelle processor.
  4b  = klein taalmodel (ca. 2,5 GB), aanbevolen voor Windows-laptops zonder losse videokaart.
#>
param(
  [string]$Doel = ".\modellen",
  [ValidateSet("12b", "4b")][string]$Llm = "4b"
)
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force $Doel | Out-Null

$regels = Get-Content (Join-Path $PSScriptRoot "modellen.tsv") | Where-Object { $_ -and $_ -notmatch '^#' }
foreach ($regel in $regels) {
  $sleutel, $bestand, $url = $regel -split "`t"
  if ($sleutel -ne "whisper" -and $sleutel -ne "llm-$Llm") { continue }
  $pad = Join-Path $Doel $bestand
  if ((Test-Path $pad) -and (Get-Item $pad).Length -gt 0) {
    Write-Host "Staat er al: $bestand"
    continue
  }
  Write-Host "Ophalen: $bestand"
  & curl.exe -L --fail --progress-bar -C - -o "$pad.deel" $url
  if ($LASTEXITCODE -ne 0) { throw "Downloaden mislukt: $url" }
  Move-Item -Force "$pad.deel" $pad
}

foreach ($gguf in Get-ChildItem $Doel -Filter *.gguf) {
  $stroom = [System.IO.File]::OpenRead($gguf.FullName)
  $kop = New-Object byte[] 4
  [void]$stroom.Read($kop, 0, 4)
  $stroom.Close()
  if ([System.Text.Encoding]::ASCII.GetString($kop) -ne "GGUF") { throw "Ongeldig modelbestand: $($gguf.Name)" }
}
Write-Host ""
Write-Host "Klaar. Modellen staan in: $Doel"
Get-ChildItem $Doel | Format-Table Name, @{ n = "GB"; e = { [math]::Round($_.Length / 1GB, 1) } }
