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
    for ($i = 1; $i -le 30; $i++) {
        try {
            $r = Invoke-WebRequest -UseBasicParsing -Uri http://localhost:8200/v1/sys/health -TimeoutSec 3 -ErrorAction Stop
            if ($r.StatusCode -eq 200) { Write-Host "OpenBao ready" -ForegroundColor Green; return $true }
        } catch {}
        Write-Host "Wait OpenBao $i/30..."
        Start-Sleep 3
    }
    return $false
}

function Get-OpenBaoContainer {
    return (docker ps -q --filter "name=my_app_openbao" | Select-Object -First 1)
}

function Bootstrap-OpenBao {
    param($SK, $AK, $DBP, $BaoContainer)
    Write-Host "Bootstrap OpenBao container=$BaoContainer..." -ForegroundColor Yellow

    $ErrorActionPreference = 'Continue'
    $PSNativeCommandUseErrorActionPreference = $false

    & docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=root $BaoContainer `
        bao kv put secret/forum/dev "SECRET_KEY=$SK" "API_KEY=$AK" "DB_PASSWORD=$DBP" 2>&1 | Out-Null

    & docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=root $BaoContainer `
        bao auth enable approle 2>&1 | Out-Null

    $policyPath = Join-Path (Get-Location) "openbao\forum-read.hcl"
    $utf8NoBomPol = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($policyPath, 'path "secret/data/forum/dev" { capabilities = ["read"] }', $utf8NoBomPol)
    & docker cp $policyPath "${BaoContainer}:/tmp/p.hcl" 2>&1 | Out-Null
    & docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=root $BaoContainer `
        bao policy write forum-read /tmp/p.hcl 2>&1 | Out-Null

    & docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=root $BaoContainer `
        bao write auth/approle/role/forum token_policies=forum-read token_ttl=1h token_max_ttl=4h 2>&1 | Out-Null

    $roleId = & docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=root $BaoContainer `
        bao read -field=role_id auth/approle/role/forum/role-id 2>$null
    $secretId = & docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=root $BaoContainer `
        bao write -f -field=secret_id auth/approle/role/forum/secret-id 2>$null

    if (-not $roleId -or -not $secretId) {
        Write-Error "Echec recuperation role_id/secret_id"
        exit 1
    }

    if (-not (Test-Path "openbao")) { New-Item -ItemType Directory -Path "openbao" | Out-Null }
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText((Resolve-Path "openbao").Path + "\role_id", $roleId.Trim(), $utf8NoBom)
    [System.IO.File]::WriteAllText((Resolve-Path "openbao").Path + "\secret_id", $secretId.Trim(), $utf8NoBom)

    Write-Host "AppRole creds ecrits" -ForegroundColor Green
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

        # Si role_id/secret_id absent, ecris placeholder (sera remplace apres bootstrap)
        if (-not (Test-Path "openbao/role_id")) { Set-Content "openbao/role_id" "placeholder" -NoNewline }
        if (-not (Test-Path "openbao/secret_id")) { Set-Content "openbao/secret_id" "placeholder" -NoNewline }

        # Cleanup state pollue d'anciens runs (network/stack residuels)
        docker stack rm my_app 2>$null | Out-Null
        Start-Sleep 12
        $oldNet = docker network ls --filter "name=my_app_frontend" -q
        if ($oldNet) {
            Write-Host "Suppression network residuel..." -ForegroundColor Yellow
            docker network rm my_app_frontend 2>$null | Out-Null
            Start-Sleep 3
        }

        # 1. Deploy stack initial (openbao + tout) - bao-agent va echouer auth, c'est OK
        Write-Host "Deploy stack initial..." -ForegroundColor Yellow
        docker stack deploy -c docker-stack.yml my_app

        # 2. Attendre OpenBao ready (port 8200 publie via Swarm ingress)
        if (-not (Wait-OpenBao)) {
            Write-Error "OpenBao pas ready"
            $bao = Get-OpenBaoContainer
            if ($bao) { docker logs $bao --tail 30 }
            exit 1
        }

        # 3. Bootstrap (idempotent)
        $baoCt = Get-OpenBaoContainer
        if (-not $baoCt) {
            Write-Error "Conteneur openbao introuvable"
            exit 1
        }
        Bootstrap-OpenBao -SK $SecretKey -AK $ApiKey -DBP $DbPassword -BaoContainer $baoCt

        # 4. Force recreate bao-agent pour relire role_id/secret_id frais
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
            Write-Host "=== Logs bao-agent ===" -ForegroundColor Red
            if ($agent) { docker logs $agent --tail 50 }
            exit 1
        }

        # 6. Force redeploy app pour qu'il lise le nouveau fichier rendu
        Write-Host "Force redeploy app..." -ForegroundColor Yellow
        docker service update --force my_app_app | Out-Null

        # 7. Attend replicas app 2/2
        for ($i = 1; $i -le 30; $i++) {
            $replicas = docker service ls --filter name=my_app_app --format "{{.Replicas}}"
            Write-Host "Replicas $i/30: $replicas"
            if ($replicas -eq "2/2") { Write-Host "Stack OK" -ForegroundColor Green; break }
            Start-Sleep 5
        }

        docker stack services my_app
        Write-Host "`nOpenBao UI:   http://localhost:8200 (token=root)" -ForegroundColor Cyan
        Write-Host "App (Nginx):   http://localhost" -ForegroundColor Cyan
        Write-Host "Uptime Kuma:  http://localhost:3001" -ForegroundColor Cyan
    }

    "rotate-bao" {
        if (-not $SecretKey -or -not $ApiKey -or -not $DbPassword) {
            Write-Error "Args requis: -SecretKey -ApiKey -DbPassword"
            return
        }
        $baoCt = Get-OpenBaoContainer
        if (-not $baoCt) { Write-Error "openbao non running"; return }
        Write-Host "Rotation via OpenBao..." -ForegroundColor Yellow
        docker exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN=root $baoCt `
            bao kv put secret/forum/dev "SECRET_KEY=$SecretKey" "API_KEY=$ApiKey" "DB_PASSWORD=$DbPassword"
        Write-Host "Agent re-render <5s, app re-read <15s. Aucun restart." -ForegroundColor Green
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
