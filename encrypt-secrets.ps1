# encrypt-secrets.ps1
# Helper local pour chiffrer secrets en fichier secrets.enc commit-able
# Usage:
#   $env:SECRETS_PASSPHRASE = "ma-phrase-secrete"
#   .\encrypt-secrets.ps1 -FlaskSecretKey "..." -UsernameDb "..." -PasswordDb "..."
#
# Apres: commit secrets.enc + ajoute SECRETS_PASSPHRASE aux GitHub Secrets

param(
    [Parameter(Mandatory=$true)] $FlaskSecretKey,
    [Parameter(Mandatory=$true)] $UsernameDb,
    [Parameter(Mandatory=$true)] $PasswordDb
)

$pass = $env:SECRETS_PASSPHRASE
if (-not $pass) {
    $pass = Read-Host -AsSecureString "Passphrase de chiffrement"
    $pass = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($pass))
}

# Plaintext format KEY=VALUE
$plain = @"
FLASK_SECRET_KEY=$FlaskSecretKey
USERNAME_DB=$UsernameDb
PASSWORD_DB=$PasswordDb
"@

# Ecris fichier temp
$tmp = [System.IO.Path]::GetTempFileName()
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($tmp, $plain, $utf8)

# Chiffre via openssl (ships with Git for Windows)
$enc = "secrets.enc"
& openssl enc -aes-256-cbc -pbkdf2 -salt -in $tmp -out $enc -pass "pass:$pass"

Remove-Item $tmp -Force
if (Test-Path $enc) {
    Write-Host "Chiffre dans $enc" -ForegroundColor Green
    Write-Host "Commit ce fichier. Ajoute SECRETS_PASSPHRASE='$pass' a GitHub Secrets." -ForegroundColor Cyan
} else {
    Write-Error "Echec chiffrement"
}
