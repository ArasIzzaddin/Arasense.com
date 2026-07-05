param(
  [Parameter(Mandatory = $true)]
  [string]$ManifestPath,

  [Parameter(Mandatory = $true)]
  [string]$GcsPrefix,

  [string]$Project = "valid-shine-488311-d6"
)

$ErrorActionPreference = "Stop"
if (-not $GcsPrefix.StartsWith("gs://")) {
  throw "GcsPrefix must start with gs://"
}

$rows = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
foreach ($row in $rows) {
  $dest = ($GcsPrefix.TrimEnd("/") + "/" + [System.IO.Path]::GetFileName($row.file))
  Write-Host "Copying $($row.file) -> $dest"
  gcloud storage cp --project $Project "$($row.file)" "$dest"
  if ($LASTEXITCODE -ne 0) {
    throw "Cloud Storage copy failed for $($row.file)"
  }
}
