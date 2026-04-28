# manage-swarm.ps1
# Orchestre OpenBao + agent + Swarm stack en local
# Lance par self-hosted runner sur push GitHub

param (
    [Parameter(Mandatory=$false)]
    [ValidateSet("init", "deploy", "rotate-bao", "status", "destroy")]
    $Action = "status"
)

# Empeche PowerShell 7+ de traiter stderr docker comme exception
$ErrorActionPreference = 'Continue'
if ($PSVersionTable.PSVersion.Major -ge 7) {
    $PSNativeCommandUseErrorActionPreference = $false
}

function Check-Swarm {
    $status = docker info --format '{{.Swarm.LocalNodeState}}'
    return $status -eq "active"
}

function Wait-OpenBao {
    # Server mode sealed -> retourne 501/503, dev mode unsealed -> 200
    # Accepte n'importe quelle reponse HTTP = container repond = up
    for ($i = 1; $i -le 30; $i++) {
        try {
            $r = Invoke-WebRequest -UseBasicParsing -Uri http://localhost:8200/v1/sys/health -TimeoutSec 3 -ErrorAction SilentlyContinue
            Write-Host "OpenBao ready (HTTP $($r.StatusCode))" -ForegroundColor Green
            return $true
        } catch [System.Net.WebException] {
            # Status code != 2xx = exception, mais container repond -> up
            $code = $_.Exception.Response.StatusCode.value__
            if ($code) {
                Write-Host "OpenBao ready (HTTP $code, sealed/uninit)" -ForegroundColor Green
                return $true
            }
        } catch {}
        Write-Host "Wait OpenBao $i/30..."
        Start-Sleep 3
    }
    return $false
}

function Get-OpenBaoContainer {
    return (docker ps -q --filter "name=my_app_openbao" | Select-Object -First 1)
}

function Auto-Unseal {
    if (-not (Test-Path "openbao/.unseal-keys")) {
        Write-Host "Pas de .unseal-keys -> Bao pas init. Lance .\init-bao.ps1 apres deploy." -ForegroundColor Yellow
        return $false
    }
    $bao = Get-OpenBaoContainer
    if (-not $bao) { return $false }

    $status = & docker exec -e BAO_ADDR=http://127.0.0.1:8200 $bao bao status 2>&1 | Out-String
    if ($status -match "Sealed\s+false") {
        Write-Host "Bao deja unsealed" -ForegroundColor Green
        return $true
    }

    $keys = (Get-Content "openbao/.unseal-keys" -Raw).Trim() -split "`n"
    foreach ($k in $keys[0..2]) {
        & docker exec -e BAO_ADDR=http://127.0.0.1:8200 $bao bao operator unseal $k.Trim() 2>&1 | Out-Null
    }
    Write-Host "Bao unsealed" -ForegroundColor Green
    return $true
}

switch ($Action) {
    "init" {
        if (Check-Swarm) {
            Write-Host "Swarm deja actif." -ForegroundColor Cyan
        } else {
            Write-Host "Init Swarm..." -ForegroundColor Yellow
            docker swarm init
        }
    }

    "deploy" {
        if (-not (Check-Swarm)) {
            Write-Host "Init Swarm..." -ForegroundColor Yellow
            docker swarm init
        }

        if (-not (Test-Path "rendered")) { New-Item -ItemType Directory -Path "rendered" | Out-Null }
        if (-not (Test-Path "openbao/role_id")) { Set-Content "openbao/role_id" "placeholder" -NoNewline }
        if (-not (Test-Path "openbao/secret_id")) { Set-Content "openbao/secret_id" "placeholder" -NoNewline }

        # Cleanup state pollue (network/stack residuels) - PRESERVE volumes
        docker stack rm my_app 2>$null | Out-Null
        Start-Sleep 12
        $oldNet = docker network ls --filter "name=my_app_frontend" -q
        if ($oldNet) {
            docker network rm my_app_frontend 2>$null | Out-Null
            Start-Sleep 3
        }

        # 1. Deploy stack (volume openbao-data persiste)
        Write-Host "Deploy stack..." -ForegroundColor Yellow
        docker stack deploy -c docker-stack.yml my_app

        # 2. Attendre OpenBao ready
        if (-not (Wait-OpenBao)) {
            Write-Error "OpenBao pas up"
            exit 1
        }

        # 3. Auto-unseal si init deja fait (.unseal-keys present)
        $unsealed = Auto-Unseal
        if (-not $unsealed) {
            Write-Host "`n=== ACTION REQUISE ===" -ForegroundColor Magenta
            Write-Host "Bao pas encore init. Lance:" -ForegroundColor Yellow
            Write-Host "  .\init-bao.ps1 -FlaskSecretKey 'xxx' -UsernameDb 'xxx' -PasswordDb 'xxx'" -ForegroundColor Yellow
            Write-Host "Puis re-lance .\manage-swarm.ps1 -Action deploy" -ForegroundColor Yellow
            exit 0
        }

        # 4. Force recreate bao-agent (relit role_id/secret_id, auth, render)
        Write-Host "Force redeploy bao-agent..." -ForegroundColor Yellow
        docker service update --force my_app_bao-agent | Out-Null

        # 5. Attend fichier rendu
        $rendered = $false
        for ($i = 1; $i -le 30; $i++) {
            if ((Test-Path "rendered/app.env") -and (Get-Item "rendered/app.env").Length -gt 50) {
                $rendered = $true
                Write-Host "Fichier rendu OK ($i*2s)" -ForegroundColor Green
                break
            }
            Start-Sleep 2
        }
        if (-not $rendered) {
            $agent = docker ps -q --filter "name=my_app_bao-agent" | Select-Object -First 1
            if ($agent) { docker logs $agent --tail 50 }
            exit 1
        }

        # 6. Force redeploy app
        Write-Host "Force redeploy app..." -ForegroundColor Yellow
        docker service update --force my_app_app | Out-Null

        # 7. Attend replicas
        for ($i = 1; $i -le 30; $i++) {
            $replicas = docker service ls --filter name=my_app_app --format "{{.Replicas}}"
            Write-Host "Replicas $i/30: $replicas"
            if ($replicas -eq "2/2") { break }
            Start-Sleep 5
        }

        docker stack services my_app
        Write-Host "`nOpenBao UI:   http://localhost:8200" -ForegroundColor Cyan
        Write-Host "App (Nginx): http://localhost" -ForegroundColor Cyan
        Write-Host "Uptime Kuma: http://localhost:3001" -ForegroundColor Cyan
    }

    "rotate-bao" {
        # Rotate via UI Bao ou API directe avec ton root token (openbao/.root-token)
        Write-Host "Rotation: utilise UI Bao http://localhost:8200 (token=cat openbao/.root-token)" -ForegroundColor Cyan
        Write-Host "Ou: docker exec my_app_openbao bao kv put secret/forum/dev FLASK_SECRET_KEY=...etc" -ForegroundColor Cyan
    }

    "status" {
        Write-Host "--- Swarm ---" -ForegroundColor Cyan
        docker node ls
        Write-Host "`n--- Services Swarm ---" -ForegroundColor Cyan
        docker service ls
        Write-Host "`n--- Fichier rendu ---" -ForegroundColor Cyan
        if (Test-Path "rendered/app.env") {
            $info = Get-Item rendered/app.env
            Write-Host "Path: $($info.FullName)"
            Write-Host "Size: $($info.Length) bytes"
            Write-Host "Modified: $($info.LastWriteTime)"
        } else {
            Write-Host "AUCUN rendered/app.env" -ForegroundColor Red
        }
    }

    "destroy" {
        Write-Host "Destruction stack..." -ForegroundColor Yellow
        docker stack rm my_app 2>$null
        Start-Sleep 10
        Write-Host "Done" -ForegroundColor Green
    }
}
