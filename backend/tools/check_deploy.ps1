# PowerShell script to verify Django production deployment check (check --deploy)
$backendDir = Split-Path -Parent $PSScriptRoot
Set-Location $backendDir

$env:DJANGO_SETTINGS_MODULE = "config.settings.prod"
$env:DJANGO_SECRET_KEY = "a-secure-production-secret-key-of-at-least-50-characters-length-xyz123"
$env:JWT_SIGNING_KEY = "jwt-signing-key-32-chars-minimum-length!"
$env:HMAC_IP_SALT = "hmac-ip-salt-32-chars-minimum-length!"
$env:INDICATOR_HMAC_KEY = "indicator-key-32-chars-minimum-length!"
$env:SCANNER_CALLBACK_SECRET = "scanner-secret-32-chars-minimum-length!"
$env:EVIDENCE_BUCKET = "scamshield-evidence-prod"
$env:ALLOWED_HOSTS = "api.scamshield.test,localhost"
$env:PUBLIC_BASE_URL = "https://scamshield.test"
$env:TRUSTED_PROXY_HOPS = "2"
$env:DB_NAME = "scamshield"
$env:DB_USER = "scamshield_user"
$env:DB_PASSWORD = "production_db_password"
$env:DB_HOST = "rds.scamshield.internal"
$env:DB_PORT = "5432"
$env:AWS_DEFAULT_REGION = "ap-southeast-1"

python manage.py check --deploy --fail-level WARNING
