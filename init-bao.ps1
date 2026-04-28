# init-bao.ps1
# A LANCER UNE SEULE FOIS apres premier deploy stack pour:
# 1. Init OpenBao (genere unseal keys + root token)
# 2. Unseal
# 3. Bootstrap secrets KV + AppRole (avec valeurs interactives)
#
# Apres init: keys sauvees dans openbao/.unseal-keys (gitignored).
# A chaque restart de openbao -> faut run unseal-bao.ps1 (auto via script wrapper).

param(
    [Parameter(Mandatory=$true)]  $FlaskSecretKey,
    [Parameter(Mandatory=$true)]  $UsernameDb,
    [Parameter(Mandatory=$true)]  $PasswordDb
)

$ErrorActionPreference = 'Continue'
if ($PSVersionTable.PSVersion.Major -ge 7) {
    $PSNativeCommandUseErrorActionPreference = $false
}

function Get-OpenBaoContainer {
    return (docker ps -q --filter "name=my_app_openbao" | Select-Object -First 1)
}

$bao = Get-OpenBaoContainer
if (-not $bao) {
    Write-Error "openbao container introuvable. Deploy stack d'abord (.\manage-swarm.ps1 deploy)."
    exit 1
}

# Attend OpenBao server ready (different de dev mode)
Write-Host "Attente OpenBao server..." -ForegroundColor Yellow
for ($i = 1; $i -le 30; $i++) {
    $status = & docker exec -e BAO_ADDR=http://127.0.0.1:8200 $bao bao status 2>&1 | Out-String
    if ($status -match "Sealed.*true|Sealed.*false") {
        Write-Host "OpenBao up (sealed=$($status -match 'Sealed.*true'))"
        break
    }
    Start-Sleep 2
}

# Init si pas deja
$status = & docker exec -e BAO_ADDR=http://127.0.0.1:8200 $bao bao status 2>&1 | Out-String
if ($status -match "Initialized\s+true") {
    Write-Host "Deja initialise. Skip init." -ForegroundColor Cyan
    if (-not (Test-Path "openbao/.unseal-keys")) {
        Write-Error "Bao initialise mais openbao/.unseal-keys manque. Tu dois recreer le volume (docker volume rm projets_openbao-data) et relancer."
        exit 1
    }
} else {
    Write-Host "Init OpenBao..." -ForegroundColor Yellow
    $initOut = & docker exec -e BAO_ADDR=http://127.0.0.1:8200 $bao bao operator init -key-shares=5 -key-threshold=3 -format=json 2>&1 | Out-String
    $initJson = $initOut | ConvertFrom-Json

    # Sauve unseal keys + root token (gitignored)
    $utf8 = New-Object System.Text.UTF8Encoding $false
    $keysFile = (Resolve-Path "openbao").Path + "\.unseal-keys"
    $tokenFile = (Resolve-Path "openbao").Path + "\.root-token"
    [System.IO.File]::WriteAllText($keysFile, ($initJson.unseal_keys_b64 -join "`n"), $utf8)
    [System.IO.File]::WriteAllText($tokenFile, $initJson.root_token, $utf8)
    Write-Host "Keys sauvees dans openbao/.unseal-keys (gitignored)" -ForegroundColor Green
}

# Lit root token
$rootToken = (Get-Content "openbao/.root-token" -Raw).Trim()

# Unseal (3 keys necessaires sur 5)
$keys = (Get-Content "openbao/.unseal-keys" -Raw).Trim() -split "`n"
Write-Host "Unseal..." -ForegroundColor Yellow
foreach ($k in $keys[0..2]) {
    & docker exec -e BAO_ADDR=http://127.0.0.1:8200 $bao bao operator unseal $k.Trim() 2>&1 | Out-Null
}

# Verifie unsealed
$status = & docker exec -e BAO_ADDR=http://127.0.0.1:8200 $bao bao status 2>&1 | Out-String
if ($status -notmatch "Sealed\s+false") {
    Write-Error "Unseal echec. Status: $status"
    exit 1
}
Write-Host "OpenBao unsealed" -ForegroundColor Green

# Bootstrap KV + AppRole (idempotent)
Write-Host "Bootstrap KV + AppRole..." -ForegroundColor Yellow

& docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=$rootToken $bao `
    bao secrets enable -path=secret kv-v2 2>&1 | Out-Null  # idempotent

& docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=$rootToken $bao `
    bao kv put secret/forum/dev "FLASK_SECRET_KEY=$FlaskSecretKey" "USERNAME_DB=$UsernameDb" "PASSWORD_DB=$PasswordDb" | Out-Null

& docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=$rootToken $bao bao auth enable approle 2>&1 | Out-Null

$policyPath = Join-Path (Get-Location) "openbao\forum-read.hcl"
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($policyPath, 'path "secret/data/forum/dev" { capabilities = ["read"] }', $utf8NoBom)
& docker cp $policyPath "${bao}:/tmp/p.hcl" 2>&1 | Out-Null
& docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=$rootToken $bao `
    bao policy write forum-read /tmp/p.hcl 2>&1 | Out-Null

& docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=$rootToken $bao `
    bao write auth/approle/role/forum token_policies=forum-read token_ttl=1h token_max_ttl=4h 2>&1 | Out-Null

$roleId = & docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=$rootToken $bao `
    bao read -field=role_id auth/approle/role/forum/role-id
$secretId = & docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=$rootToken $bao `
    bao write -f -field=secret_id auth/approle/role/forum/secret-id

[System.IO.File]::WriteAllText((Resolve-Path "openbao").Path + "\role_id", $roleId.Trim(), $utf8NoBom)
[System.IO.File]::WriteAllText((Resolve-Path "openbao").Path + "\secret_id", $secretId.Trim(), $utf8NoBom)

Write-Host "Bootstrap fini. Secrets persistes dans volume openbao-data." -ForegroundColor Green
Write-Host "Restart openbao -> faut juste unseal (run .\unseal-bao.ps1)" -ForegroundColor Cyan
