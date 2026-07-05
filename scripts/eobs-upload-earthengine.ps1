param(
  [Parameter(Mandatory = $true)]
  [string]$ManifestPath,

  [string]$Project = "valid-shine-488311-d6",

  [Parameter(Mandatory = $true)]
  [string]$GcsPrefix
)

$ErrorActionPreference = "Stop"
$rows = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
foreach ($row in $rows) {
  $date = [datetime]::Parse($row.date)
  $millis = [int64](($date.ToUniversalTime() - [datetime]'1970-01-01T00:00:00Z').TotalMilliseconds)
  $source = ($GcsPrefix.TrimEnd("/") + "/" + [System.IO.Path]::GetFileName($row.file))
  if (-not $source.StartsWith("gs://")) {
    throw "GcsPrefix must start with gs:// because Earth Engine upload requires Cloud Storage sources."
  }
  Write-Host "Uploading $source -> $($row.asset_id)"
  earthengine --project $Project upload image `
    --asset_id="$($row.asset_id)" `
    --time_start=$millis `
    --property="dataset=E-OBS" `
    --property="variable=$($row.band)" `
    --bands="$($row.band)" `
    "$source"
  if ($LASTEXITCODE -ne 0) {
    throw "Earth Engine upload failed for $source"
  }
}
