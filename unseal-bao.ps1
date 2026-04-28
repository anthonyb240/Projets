# unseal-bao.ps1
# A LANCER apres chaque restart d'openbao (apres docker stack deploy)
# Lit openbao/.unseal-keys et unseal automatique

$ErrorActionPreference = 'Continue'
if ($PSVersionTable.PSVersion.Major -ge 7) {
    $PSNativeCommandUseErrorActionPreference = $false
}

if (-not (Test-Path "openbao/.unseal-keys")) {
    Write-Error "openbao/.unseal-keys absent. Run init-bao.ps1 d'abord."
    exit 1
}

$bao = docker ps -q --filter "name=my_app_openbao" | Select-Object -First 1
if (-not $bao) {
    Write-Error "openbao container introuvable"
    exit 1
}

# Wait container ready
Write-Host "Attente OpenBao..." -ForegroundColor Yellow
for ($i = 1; $i -le 30; $i++) {
    $status = & docker exec -e BAO_ADDR=http://127.0.0.1:8200 $bao bao status 2>&1 | Out-String
    if ($status -match "Sealed") { break }
    Start-Sleep 2
}

# Already unsealed?
if ($status -match "Sealed\s+false") {
    Write-Host "Deja unsealed, rien a faire" -ForegroundColor Green
    exit 0
}

# Unseal avec 3 cles
$keys = (Get-Content "openbao/.unseal-keys" -Raw).Trim() -split "`n"
Write-Host "Unseal avec 3 cles..." -ForegroundColor Yellow
foreach ($k in $keys[0..2]) {
    & docker exec -e BAO_ADDR=http://127.0.0.1:8200 $bao bao operator unseal $k.Trim() 2>&1 | Out-Null
}

# Verif
$status = & docker exec -e BAO_ADDR=http://127.0.0.1:8200 $bao bao status 2>&1 | Out-String
if ($status -match "Sealed\s+false") {
    Write-Host "OpenBao unsealed" -ForegroundColor Green
} else {
    Write-Error "Unseal echec"
    exit 1
}
