param(
  [Parameter(Mandatory = $true)]
  [string]$FlaskSecretKey,

  [Parameter(Mandatory = $true)]
  [string]$UsernameDb,

  [Parameter(Mandatory = $true)]
  [string]$PasswordDb
)

$ErrorActionPreference = "Stop"

Write-Host "Attente OpenBao server..."

$baoContainer = docker ps --filter "name=my_app_openbao" --format "{{.Names}}" | Select-Object -First 1

if (-not $baoContainer) {
  Write-Error "Conteneur OpenBao introuvable. Verifie: docker ps"
  exit 1
}

Write-Host "Conteneur OpenBao: $baoContainer"

function Invoke-Bao {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Command
  )

  $out = docker exec $baoContainer sh -lc "export BAO_ADDR=http://127.0.0.1:8200; $Command" 2>&1

  if ($LASTEXITCODE -ne 0) {
    Write-Error "Commande Bao echouee: $Command`n$out"
    exit 1
  }

  return $out
}

# Attente disponibilite OpenBao
$ready = $false

for ($i = 1; $i -le 60; $i++) {
  $statusOut = docker exec $baoContainer sh -lc "export BAO_ADDR=http://127.0.0.1:8200; bao status -format=json" 2>&1

  if ($LASTEXITCODE -eq 0 -or $statusOut -match "sealed|initialized|Initialized|Sealed") {
    $ready = $true
    break
  }

  Write-Host "Attente OpenBao... tentative $i/60"
  Start-Sleep -Seconds 2
}

if (-not $ready) {
  Write-Error "OpenBao ne repond pas."
  exit 1
}

# Status JSON
$statusRaw = docker exec $baoContainer sh -lc "export BAO_ADDR=http://127.0.0.1:8200; bao status -format=json" 2>&1

try {
  $status = $statusRaw | ConvertFrom-Json
} catch {
  Write-Error "Impossible de parser le status OpenBao en JSON. Sortie:`n$statusRaw"
  exit 1
}

Write-Host "OpenBao up initialized=$($status.initialized) sealed=$($status.sealed)"

if ($status.initialized -eq $false) {
  Write-Host "Init OpenBao..."

  $initRaw = docker exec $baoContainer sh -lc "export BAO_ADDR=http://127.0.0.1:8200; bao operator init -key-shares=5 -key-threshold=3 -format=json" 2>&1

  if ($LASTEXITCODE -ne 0) {
    Write-Error "Init OpenBao echouee. Sortie:`n$initRaw"
    exit 1
  }

  try {
    $initJson = $initRaw | ConvertFrom-Json
  } catch {
    Write-Error "Init OpenBao n'a pas retourne du JSON valide. Sortie:`n$initRaw"
    exit 1
  }

  if (-not $initJson.unseal_keys_b64 -or -not $initJson.root_token) {
    Write-Error "Init OpenBao incomplete. Sortie:`n$initRaw"
    exit 1
  }

  $initJson.unseal_keys_b64 | Set-Content -Path "openbao/.unseal-keys" -Encoding ASCII
  $initJson.root_token | Set-Content -Path "openbao/.root-token" -Encoding ASCII

  Write-Host "Keys sauvees dans openbao/.unseal-keys"
  Write-Host "Root token sauve dans openbao/.root-token"
} else {
  Write-Host "OpenBao deja initialise."
}

if (-not (Test-Path "openbao/.unseal-keys")) {
  Write-Error "ERREUR: OpenBao est deja initialise mais les cles locales (.unseal-keys) sont absentes. Impossible de desceller (unseal).`nSolution: Si vous voulez repartir de zero, lancez: .\manage-swarm.ps1 -Action reset-bao"
  exit 1
}

if (-not (Test-Path "openbao/.root-token")) {
  Write-Error "openbao/.root-token absent apres init."
  exit 1
}

$rootToken = (Get-Content "openbao/.root-token" -Raw).Trim()
$keys = Get-Content "openbao/.unseal-keys" | Where-Object { $_.Trim() -ne "" }

if ($keys.Count -lt 3) {
  Write-Error "Pas assez de cles unseal. Nombre trouve: $($keys.Count)"
  exit 1
}

Write-Host "::add-mask::$rootToken"

foreach ($k in $keys) {
  Write-Host "::add-mask::$k"
}

# Unseal si necessaire
$statusRaw = docker exec $baoContainer sh -lc "export BAO_ADDR=http://127.0.0.1:8200; bao status -format=json" 2>&1
$status = $statusRaw | ConvertFrom-Json

if ($status.sealed -eq $true) {
  Write-Host "Unseal..."

  foreach ($k in $keys[0..2]) {
    $unsealOut = docker exec $baoContainer sh -lc "export BAO_ADDR=http://127.0.0.1:8200; bao operator unseal '$k'" 2>&1

    if ($LASTEXITCODE -ne 0) {
      Write-Error "Unseal echoue. Sortie:`n$unsealOut"
      exit 1
    }
  }
} else {
  Write-Host "OpenBao deja unsealed."
}

# Verification finale unseal
$statusRaw = docker exec $baoContainer sh -lc "export BAO_ADDR=http://127.0.0.1:8200; bao status -format=json" 2>&1
$status = $statusRaw | ConvertFrom-Json

if ($status.sealed -eq $true) {
  Write-Error "Unseal echec. OpenBao est encore sealed."
  exit 1
}

Write-Host "OpenBao unsealed OK"

# Configuration secrets
Write-Host "Configuration KV et secrets..."

# Enable KV v2 si pas deja present.
# Si deja active, on ignore l'erreur "path is already in use".
$enableOut = docker exec $baoContainer sh -lc "export BAO_ADDR=http://127.0.0.1:8200; export BAO_TOKEN='$rootToken'; bao secrets enable -path=secret kv-v2" 2>&1

if ($LASTEXITCODE -ne 0 -and ($enableOut | Out-String) -notmatch "path is already in use") {
  Write-Error "Activation KV echouee. Sortie:`n$enableOut"
  exit 1
}

# Ecriture des secrets au chemin attendu par l'agent:
# CLI KV v2: secret/forum/dev
# API/policy: secret/data/forum/dev
$encodedFlask = $FlaskSecretKey.Replace("'", "'\''")
$encodedUser = $UsernameDb.Replace("'", "'\''")
$encodedPass = $PasswordDb.Replace("'", "'\''")

$putOut = docker exec $baoContainer sh -lc "export BAO_ADDR=http://127.0.0.1:8200; export BAO_TOKEN='$rootToken'; bao kv put secret/forum/dev FLASK_SECRET_KEY='$encodedFlask' USERNAME_DB='$encodedUser' PASSWORD_DB='$encodedPass'" 2>&1

if ($LASTEXITCODE -ne 0) {
  Write-Error "Ecriture secrets echouee. Sortie:`n$putOut"
  exit 1
}

Write-Host "Secrets ecrits dans secret/forum/dev"

# AppRole pour l'agent
Write-Host "Configuration AppRole..."

$authOut = docker exec $baoContainer sh -lc "export BAO_ADDR=http://127.0.0.1:8200; export BAO_TOKEN='$rootToken'; bao auth enable approle" 2>&1

if ($LASTEXITCODE -ne 0 -and ($authOut | Out-String) -notmatch "path is already in use") {
  Write-Error "Activation AppRole echouee. Sortie:`n$authOut"
  exit 1
}

$policy = @'
path "secret/data/forum/dev" {
  capabilities = ["read"]
}
'@

$policyFile = [System.IO.Path]::GetTempFileName()
$policy | Set-Content -Path $policyFile -Encoding ASCII

docker cp $policyFile "${baoContainer}:/tmp/forum-read.hcl"
Remove-Item $policyFile -Force -ErrorAction SilentlyContinue

if ($LASTEXITCODE -ne 0) {
  Write-Error "Copie policy dans le conteneur echouee."
  exit 1
}

$policyOut = docker exec $baoContainer sh -lc "export BAO_ADDR=http://127.0.0.1:8200; export BAO_TOKEN='$rootToken'; bao policy write forum-read /tmp/forum-read.hcl" 2>&1

if ($LASTEXITCODE -ne 0) {
  Write-Error "Creation policy echouee. Sortie:`n$policyOut"
  exit 1
}

$roleOut = docker exec $baoContainer sh -lc "export BAO_ADDR=http://127.0.0.1:8200; export BAO_TOKEN='$rootToken'; bao write auth/approle/role/forum token_policies=forum-read token_ttl=1h token_max_ttl=4h" 2>&1

if ($LASTEXITCODE -ne 0) {
  Write-Error "Creation role AppRole echouee. Sortie:`n$roleOut"
  exit 1
}

$roleId = docker exec $baoContainer sh -lc "export BAO_ADDR=http://127.0.0.1:8200; export BAO_TOKEN='$rootToken'; bao read -field=role_id auth/approle/role/forum/role-id" 2>&1

if ($LASTEXITCODE -ne 0) {
  Write-Error "Lecture role_id echouee. Sortie:`n$roleId"
  exit 1
}

$secretId = docker exec $baoContainer sh -lc "export BAO_ADDR=http://127.0.0.1:8200; export BAO_TOKEN='$rootToken'; bao write -f -field=secret_id auth/approle/role/forum/secret-id" 2>&1

if ($LASTEXITCODE -ne 0) {
  Write-Error "Generation secret_id echouee. Sortie:`n$secretId"
  exit 1
}

$roleId = ($roleId | Out-String).Trim()
$secretId = ($secretId | Out-String).Trim()

if (-not $roleId) {
  Write-Error "role_id vide."
  exit 1
}

if (-not $secretId) {
  Write-Error "secret_id vide."
  exit 1
}

Write-Host "::add-mask::$roleId"
Write-Host "::add-mask::$secretId"

$roleId | Set-Content -Path "openbao/role_id" -Encoding ASCII
$secretId | Set-Content -Path "openbao/secret_id" -Encoding ASCII

Write-Host "AppRole OK"
Write-Host "role_id et secret_id sauvegardes"
Write-Host "Init Bao terminee avec succes"