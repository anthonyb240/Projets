param(
  [Parameter(Mandatory = $true)]
  [string]$FlaskSecretKey,

  [Parameter(Mandatory = $true)]
  [string]$UsernameDb,

  [Parameter(Mandatory = $true)]
  [string]$PasswordDb
)

$ErrorActionPreference = "Stop"

if (-not $env:SECRETS_PASSPHRASE) {
  Write-Error "SECRETS_PASSPHRASE manquant. Exemple: `$env:SECRETS_PASSPHRASE = 'ma-passphrase-forte'"
  exit 1
}

Write-Host "::add-mask::$env:SECRETS_PASSPHRASE"

$opensslCandidates = @(
  "openssl",
  "C:\Program Files\Git\usr\bin\openssl.exe",
  "C:\Program Files\OpenSSL-Win64\bin\openssl.exe",
  "C:\Program Files\OpenSSL-Win32\bin\openssl.exe"
)

$openssl = $null

foreach ($candidate in $opensslCandidates) {
  try {
    & $candidate version *> $null
    $openssl = $candidate
    break
  } catch {}
}

if (-not $openssl) {
  Write-Error "OpenSSL introuvable. Installe Git for Windows ou OpenSSL."
  exit 1
}

Write-Host "OpenSSL trouve: $openssl"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$enc = Join-Path $repoRoot "secrets.enc"
$tmp = [System.IO.Path]::GetTempFileName()

try {
  @"
FLASK_SECRET_KEY=$FlaskSecretKey
USERNAME_DB=$UsernameDb
PASSWORD_DB=$PasswordDb
"@ | Set-Content -Path $tmp -Encoding UTF8 -NoNewline

  Write-Host "::add-mask::$FlaskSecretKey"
  Write-Host "::add-mask::$UsernameDb"
  Write-Host "::add-mask::$PasswordDb"

  & $openssl enc -aes-256-cbc -pbkdf2 -salt `
    -in $tmp `
    -out $enc `
    -pass "pass:$env:SECRETS_PASSPHRASE"

  if ($LASTEXITCODE -ne 0) {
    Write-Error "Chiffrement echoue."
    exit 1
  }

  Write-Host "OK: secrets.enc genere: $enc"
  Write-Host "Commit ce fichier: git add secrets.enc && git commit -m `"update encrypted secrets`""
  Write-Host "Ajoute/maj SECRETS_PASSPHRASE dans GitHub Secrets avec la meme passphrase."
}
finally {
  Remove-Item $tmp -Force -ErrorAction SilentlyContinue
}