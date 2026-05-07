param(
    [string]$ServiceName = "arasense-api",
    [string]$Region = "us-central1",
    [string]$ProjectId = "valid-shine-488311-d6",
    [string]$EnvFile = "env.cloudrun.yaml"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    throw "gcloud is not installed or not available in PATH."
}

if (-not (Test-Path $EnvFile)) {
    throw "Missing env file: $EnvFile"
}

gcloud config set project $ProjectId
gcloud run deploy $ServiceName `
  --source . `
  --region $Region `
  --allow-unauthenticated `
  --env-vars-file $EnvFile
