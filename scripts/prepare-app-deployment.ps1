param(
    [string]$ProjectId = "valid-shine-488311-d6",
    [string]$CloudRunUrl = "https://REPLACE_WITH_CLOUD_RUN_URL",
    [string]$MonthlyApiLimit = "100"
)

$ErrorActionPreference = "Stop"

function New-Secret([int]$Bytes = 32) {
    $buffer = New-Object byte[] $Bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($buffer)
    } finally {
        $rng.Dispose()
    }
    return [Convert]::ToBase64String($buffer).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$envPath = Join-Path $root "env.cloudrun.yaml"
$workerDir = Join-Path $root "cloudflare-worker"
$workerPath = Join-Path $workerDir "wrangler.toml"

if (-not (Test-Path $workerDir)) {
    throw "Missing worker directory: $workerDir"
}

$originSecret = New-Secret 32
$inviteCode = New-Secret 18
$sessionToken = New-Secret 32

if (-not (Test-Path $envPath)) {
    @"
ARASENSE_GCP_PROJECT: "$ProjectId"
GCP_SERVICE_ACCOUNT_JSON: '{"type":"service_account","project_id":"$ProjectId","private_key_id":"REPLACE_ME","private_key":"-----BEGIN PRIVATE KEY-----\nREPLACE_ME\n-----END PRIVATE KEY-----\n","client_email":"REPLACE_ME","client_id":"REPLACE_ME","token_uri":"https://oauth2.googleapis.com/token"}'
ARASENSE_BACKEND_SHARED_SECRET: "$originSecret"
ARASENSE_APP_DISABLED: "false"
ARASENSE_APP_DISABLED_MESSAGE: "The current demo usage limit has been reached. The public website remains online."
"@ | Set-Content -LiteralPath $envPath -Encoding utf8
    Write-Output "Created env.cloudrun.yaml"
} else {
    Write-Output "Skipped env.cloudrun.yaml because it already exists"
}

if (-not (Test-Path $workerPath)) {
    @"
name = "arasense-app-gateway"
main = "worker.js"
compatibility_date = "2026-06-06"

routes = [
  { pattern = "app.arasense.com/*", zone_name = "arasense.com" }
]

kv_namespaces = [
  { binding = "ARASENSE_USAGE", id = "REPLACE_WITH_KV_NAMESPACE_ID" }
]

[vars]
ORIGIN_URL = "$CloudRunUrl"
APP_INVITE_CODE = "$inviteCode"
APP_SESSION_TOKEN = "$sessionToken"
ORIGIN_SHARED_SECRET = "$originSecret"
MONTHLY_API_LIMIT = "$MonthlyApiLimit"
USAGE_KEY_PREFIX = "arasense-prod"
"@ | Set-Content -LiteralPath $workerPath -Encoding utf8
    Write-Output "Created cloudflare-worker/wrangler.toml"
    Write-Output "Invite code: $inviteCode"
} else {
    Write-Output "Skipped cloudflare-worker/wrangler.toml because it already exists"
}

Write-Output "Next: replace GCP_SERVICE_ACCOUNT_JSON in env.cloudrun.yaml with the real service-account JSON."
Write-Output "Next: create the Cloudflare KV namespace and replace REPLACE_WITH_KV_NAMESPACE_ID in cloudflare-worker/wrangler.toml."
