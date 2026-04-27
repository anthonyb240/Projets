# manage-swarm.ps1
# Script utilitaire pour gérer Docker Swarm, les secrets et les déploiements

param (
    [Parameter(Mandatory=$false)]
    [ValidateSet("init", "deploy", "rotate-secret", "blue-green-switch", "status")]
    $Action = "status",

    [Parameter(Mandatory=$false)]
    $SecretValue = "",

    [Parameter(Mandatory=$false)]
    $TargetColor = "blue"
)

function Check-Swarm {
    $status = docker info --format '{{.Swarm.LocalNodeState}}'
    return $status -eq "active"
}

switch ($Action) {
    "init" {
        if (Check-Swarm) {
            Write-Host "Docker Swarm est déjà actif." -ForegroundColor Cyan
        } else {
            Write-Host "Initialisation de Docker Swarm..." -ForegroundColor Yellow
            docker swarm init
        }
    }

    "deploy" {
        Write-Host "Déploiement du stack 'my_app'..." -ForegroundColor Yellow
        # S'assurer que le secret par défaut existe pour le premier déploiement
        if (-not (docker secret ls --filter "name=app_secret_v1" -q)) {
            Write-Host "Création du secret initial app_secret_v1..."
            "SECRET_KEY=initial-swarm-key-123" | docker secret create app_secret_v1 -
        }
        docker stack deploy -c docker-stack.yml my_app
    }

    "rotate-secret" {
        if (-not $SecretValue) {
            Write-Error "Vous devez fournir -SecretValue pour la rotation."
            return
        }

        # Déterminer la nouvelle version
        $existing = docker secret ls --filter "name=app_secret_v" --format "{{.Name}}"
        $latestVersion = 1
        foreach ($name in $existing) {
            if ($name -match "v(\d+)") {
                $v = [int]$matches[1]
                if ($v -gt $latestVersion) { $latestVersion = $v }
            }
        }
        $newVersion = $latestVersion + 1
        $newName = "app_secret_v$newVersion"

        Write-Host "Rotation du secret : Création de $newName..." -ForegroundColor Yellow
        $SecretValue | docker secret create $newName -

        Write-Host "Mise à jour du service pour utiliser le nouveau secret..."
        # On met à jour le fichier stack.yml (ou on utilise docker service update)
        # Ici on montre la commande directe pour la rotation immédiate
        docker service update `
            --secret-rm app_secret_v$latestVersion `
            --secret-add source=$newName,target=app_secret `
            my_app_app
        
        Write-Host "Rotation terminée. Swarm effectue un Rolling Update." -ForegroundColor Green
    }

    "blue-green-switch" {
        Write-Host "Bascule Blue-Green vers $TargetColor..." -ForegroundColor Yellow
        # Logique de modification de nginx.conf pour changer l'upstream
        $confPath = "nginx.conf"
        $content = Get-Content $confPath
        
        if ($TargetColor -eq "green") {
            $content = $content -replace 'server app:5000;', 'server app_green:5000;'
            Write-Host "Configuration Nginx mise à jour vers GREEN."
        } else {
            $content = $content -replace 'server app_green:5000;', 'server app:5000;'
            Write-Host "Configuration Nginx mise à jour vers BLUE (Default)."
        }
        
        $content | Set-Content $confPath
        
        # Recharger Nginx
        docker service update --force my_app_nginx
        Write-Host "Bascule effectuée." -ForegroundColor Green
    }

    "status" {
        Write-Host "--- Etat du Cluster Swarm ---" -ForegroundColor Cyan
        docker node ls
        Write-Host "`n--- Services actifs ---" -ForegroundColor Cyan
        docker service ls
        Write-Host "`n--- Secrets enregistrés ---" -ForegroundColor Cyan
        docker secret ls
    }
}
