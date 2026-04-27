# manage-swarm.ps1
# Orchestre OpenBao + agent + Swarm stack en local
# Lance par self-hosted runner sur push GitHub

param (
    [Parameter(Mandatory=$false)]
    [ValidateSet("init", "deploy", "rotate-bao", "status", "destroy")]
    $Action = "status",

    [Parameter(Mandatory=$false)]
    $SecretKey = "",
    [Parameter(Mandatory=$false)]
    $ApiKey = "",
    [Parameter(Mandatory=$false)]
    $DbPassword = ""
)

function Check-Swarm {
    $status = docker info --format '{{.Swarm.LocalNodeState}}'
    return $status -eq "active"
}

function Wait-OpenBao {
    for ($i = 1; $i -le 20; $i++) {
        try {
            $r = Invoke-WebRequest -UseBasicParsing -Uri http://localhost:8200/v1/sys/health -TimeoutSec 3 -ErrorAction Stop
            if ($r.StatusCode -eq 200) { Write-Host "OpenBao ready" -ForegroundColor Green; return $true }
        } catch {}
        Start-Sleep 2
    }
    return $false
}

function Bootstrap-OpenBao {
    param($SK, $AK, $DBP)
    Write-Host "Bootstrap OpenBao..." -ForegroundColor Yellow

    # Suppress PowerShell NativeCommandError sur docker stderr
    $ErrorActionPreference = 'Continue'
    $PSNativeCommandUseErrorActionPreference = $false

    # KV v2 deja monte en mode dev
    & docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=root openbao `
        bao kv put secret/forum/dev "SECRET_KEY=$SK" "API_KEY=$AK" "DB_PASSWORD=$DBP" 2>&1 | Out-Null

    # Active AppRole (idempotent - ignore erreur si deja enabled)
    & docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=root openbao `
        bao auth enable approle 2>&1 | Out-Null

    # Policy
    $policy = "path `"secret/data/forum/dev`" { capabilities = [`"read`"] }"
    & docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=root openbao `
        sh -c "echo '$policy' > /tmp/p.hcl && bao policy write forum-read /tmp/p.hcl" 2>&1 | Out-Null

    # Role
    & docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=root openbao `
        bao write auth/approle/role/forum token_policies=forum-read token_ttl=1h token_max_ttl=4h 2>&1 | Out-Null

    # Recupere creds
    $roleId = & docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=root openbao `
        bao read -field=role_id auth/approle/role/forum/role-id 2>$null
    $secretId = & docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=root openbao `
        bao write -f -field=secret_id auth/approle/role/forum/secret-id 2>$null

    if (-not $roleId -or -not $secretId) {
        Write-Error "Echec recuperation role_id/secret_id"
        exit 1
    }

    if (-not (Test-Path "openbao")) { New-Item -ItemType Directory -Path "openbao" | Out-Null }
    # IMPORTANT: ASCII no BOM (PS 5.1 default = UTF-16 BOM, casse l'auth Bao)
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText((Resolve-Path "openbao").Path + "\role_id", $roleId.Trim(), $utf8NoBom)
    [System.IO.File]::WriteAllText((Resolve-Path "openbao").Path + "\secret_id", $secretId.Trim(), $utf8NoBom)

    # Hexdump 4 premiers octets pour debug encoding
    $bytes = [System.IO.File]::ReadAllBytes((Resolve-Path "openbao").Path + "\role_id") | Select-Object -First 8
    Write-Host "role_id first bytes: $($bytes -join ' ')" -ForegroundColor DarkGray

    Write-Host "AppRole creds ecrits (UTF-8 no BOM)" -ForegroundColor Green
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
        # Defaults si args vides (CI fallback)
        if (-not $SecretKey) { $SecretKey = "deploy-fallback-flask-key-32chars-1234567890" }
        if (-not $ApiKey) { $ApiKey = "deploy-fallback-api-key" }
        if (-not $DbPassword) { $DbPassword = "deploy-fallback-db-pass" }

        if (-not (Check-Swarm)) {
            Write-Host "Init Swarm..." -ForegroundColor Yellow
            docker swarm init
        }

        # Prepare dossiers
        if (-not (Test-Path "rendered")) { New-Item -ItemType Directory -Path "rendered" | Out-Null }

        # 1. Demarre OpenBao backend
        Write-Host "Demarrage OpenBao..." -ForegroundColor Yellow
        docker compose -f docker-compose.openbao.yml up -d openbao

        if (-not (Wait-OpenBao)) {
            Write-Error "OpenBao pas ready"
            docker logs openbao --tail 30
            exit 1
        }

        # 2. Bootstrap (idempotent)
        Bootstrap-OpenBao -SK $SecretKey -AK $ApiKey -DBP $DbPassword

        # 3. Demarre agent (force recreate pour relire role_id/secret_id frais)
        Write-Host "Demarrage bao-agent (force recreate)..." -ForegroundColor Yellow
        docker compose -f docker-compose.openbao.yml up -d --force-recreate bao-agent

        # Attend fichier rendu
        $rendered = $false
        for ($i = 1; $i -le 15; $i++) {
            if ((Test-Path "rendered/app.env") -and (Get-Item "rendered/app.env").Length -gt 50) {
                $rendered = $true
                Write-Host "Fichier rendu OK ($i*2s)" -ForegroundColor Green
                break
            }
            Start-Sleep 2
        }
        if (-not $rendered) {
            Write-Host "=== Logs bao-agent ===" -ForegroundColor Red
            docker logs bao-agent --tail 50
            Write-Host "=== Contenu role_id ===" -ForegroundColor Red
            Get-Content openbao/role_id
            Write-Host "=== rendered/ files ===" -ForegroundColor Red
            Get-ChildItem rendered/ -Force
            Write-Error "Fichier rendered/app.env vide"
            exit 1
        }

        # 4. Deploy Swarm stack
        Write-Host "Deploy Swarm stack..." -ForegroundColor Yellow
        docker stack deploy -c docker-stack.yml my_app

        # 5. Attend replicas
        for ($i = 1; $i -le 30; $i++) {
            $replicas = docker service ls --filter name=my_app_app --format "{{.Replicas}}"
            Write-Host "Tentative $i/30: replicas=$replicas"
            if ($replicas -eq "2/2") { Write-Host "Stack OK" -ForegroundColor Green; break }
            Start-Sleep 5
        }

        # 6. Status final
        docker stack services my_app
        Write-Host "`nOpenBao UI: http://localhost:8200 (token=root)" -ForegroundColor Cyan
        Write-Host "App: http://localhost (Nginx -> Swarm app)" -ForegroundColor Cyan
        Write-Host "Uptime Kuma: http://localhost:3001" -ForegroundColor Cyan
    }

    "rotate-bao" {
        if (-not $SecretKey -or -not $ApiKey -or -not $DbPassword) {
            Write-Error "Args requis: -SecretKey -ApiKey -DbPassword"
            return
        }
        Write-Host "Rotation via OpenBao..." -ForegroundColor Yellow
        docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=root openbao `
            bao kv put secret/forum/dev SECRET_KEY=$SecretKey API_KEY=$ApiKey DB_PASSWORD=$DbPassword
        Write-Host "Agent re-render <5s, app re-read <15s. Aucun restart." -ForegroundColor Green
    }

    "status" {
        Write-Host "--- Swarm ---" -ForegroundColor Cyan
        docker node ls
        Write-Host "`n--- Services Swarm ---" -ForegroundColor Cyan
        docker service ls
        Write-Host "`n--- OpenBao ---" -ForegroundColor Cyan
        docker ps --filter "name=openbao" --filter "name=bao-agent" --format "table {{.Names}}`t{{.Status}}`t{{.Ports}}"
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
        Write-Host "Destruction stack + OpenBao..." -ForegroundColor Yellow
        docker stack rm my_app 2>$null
        Start-Sleep 10
        docker compose -f docker-compose.openbao.yml down -v 2>$null
        Write-Host "Done" -ForegroundColor Green
    }
}
