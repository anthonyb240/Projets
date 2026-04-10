# Forum Flask - Pipeline CI/CD Securisee

Application web de forum construite avec Flask, integrant une pipeline CI/CD securisee de A a Z avec GitHub Actions.

## Architecture de la pipeline

```
push / PR sur dev ou main
        |
   +---------+
   | changes |  --> Detecte si des fichiers Python/Docker ont change
   +---------+
        |
   +----+----+-----------+
   |         |           |
gitleaks  trufflehog   lint (Flake8)
   |         |           |
   +---------+     +-----+-----+---------+
                   |           |         |
              sast-bandit  sast-semgrep  sca (pip-audit)
                   |           |         |
                   +-----+-----+---------+
                         |
                    trivy-fs (scan pre-build)
                         |
                  docker-build-scan (build + Trivy image)
                         |
                  dast-wapiti (docker-compose + Wapiti)
                         |
                  docker-push (deploy DockerHub)
                    [main only]
```

## Labs implementes

### Lab 1 - Qualite & Secrets

| Outil | Role | Status |
|-------|------|--------|
| **Flake8** | Linting Python (max-line-length=120) | Obligatoire |
| **Gitleaks** | Detection de secrets dans le code et l'historique Git | Obligatoire |
| **gitleaks.toml** | Regle custom avec regex pour tokens `vc_*` | Bonus |
| **TruffleHog** | Alternative a Gitleaks (detection de secrets verifies) | Bonus |

### Lab 2 - SAST & SCA

| Outil | Role | Status |
|-------|------|--------|
| **Bandit** | SAST - Analyse statique de securite Python | Obligatoire |
| **pip-audit** | SCA - Audit des dependances (CVE connues) | Obligatoire |
| **Semgrep** | SAST complementaire avec regles `auto` | Bonus |
| **Regles custom Semgrep** | Policy-as-code (voir ci-dessous) | Challenge |

#### Regles custom Semgrep (`.semgrep/custom-rules.yml`)

- `no-debug-true` : Interdit `debug=True` en production
- `no-md5-usage` : Interdit `hashlib.md5()` (obsolete)
- `no-hardcoded-secret-key` : Interdit les SECRET_KEY en dur
- `no-shell-true-subprocess` : Interdit `shell=True` dans subprocess
- `no-eval` / `no-exec` : Interdit `eval()` et `exec()`

### Lab 3 - Docker & Image Security

| Outil | Role | Status |
|-------|------|--------|
| **Dockerfile** | Image basee sur `python:3.12-slim` | Obligatoire |
| **Docker Build** | Construction de l'image dans la pipeline | Obligatoire |
| **Trivy (filesystem)** | Scan pre-build du code source | Bonus |
| **Trivy (image)** | Scan post-build de l'image Docker | Obligatoire |

### Lab 4 - DAST & Deploy

| Outil | Role | Status |
|-------|------|--------|
| **Wapiti** | Scan DAST de l'application en cours d'execution (remplace Nikto) | Bonus |
| **docker-compose** | Demarrage de l'application via `docker compose up` dans la pipeline | Bonus |
| **DockerHub Push** | Deploy de l'image sur DockerHub (branche `main` uniquement) | Obligatoire |
| **Artefacts** | Tous les rapports sont exportes en artefacts GitHub | Bonus |

### Lab 5 - CI/CD Intelligente

| Fonctionnalite | Description |
|----------------|-------------|
| **Detection de changements** | `dorny/paths-filter` pour ne lancer les tests que si des `.py` ou `requirements.txt` changent |
| **Execution conditionnelle** | Les jobs SAST/SCA/Lint ne tournent que si du code Python a ete modifie |
| **Dependances entre jobs** | `needs` pour garantir l'ordre : secrets -> lint -> SAST/SCA -> Trivy -> Docker -> DAST -> Deploy |
| **Parallelisation** | Gitleaks/TruffleHog en parallele, Bandit/Semgrep/pip-audit en parallele |
| **Cache pip** | `actions/cache@v4` pour accelerer les installations pip |

## Artefacts generes

Chaque execution de la pipeline produit les rapports suivants, telechargeables depuis l'onglet Actions de GitHub :

| Artefact | Format | Description |
|----------|--------|-------------|
| `bandit-report` | JSON | Resultats de l'analyse SAST Bandit |
| `semgrep-reports` | JSON | Resultats Semgrep (regles par defaut + custom) |
| `trivy-fs-report` | TXT | Scan Trivy du filesystem (pre-build) |
| `trivy-image-report` | TXT | Scan Trivy de l'image Docker (post-build) |
| `wapiti-report` | HTML | Resultats du scan DAST Wapiti |

## Configuration requise

### Secrets GitHub

Configurer dans **Settings > Secrets and variables > Actions** :

| Secret | Description |
|--------|-------------|
| `DOCKERHUB_USERNAME` | Nom d'utilisateur DockerHub |
| `DOCKERHUB_TOKEN` | Token d'acces DockerHub |
| `CTF_FLAG` | Flag CTF pour le build Docker |
| `DB_PASSWORD` | Mot de passe DB pour le build Docker |
| `API_KEY` | Cle API pour le build Docker |

> `GITHUB_TOKEN` est fourni automatiquement par GitHub Actions.

## Lancer le projet en local

```bash
# Installer les dependances
pip install -r requirements.txt

# Initialiser la base de donnees
python init_db.py

# Lancer le serveur
python app.py
```

## Stack technique

- **Backend** : Flask 3.1, Flask-SQLAlchemy, Flask-Login, Flask-WTF, Flask-Talisman
- **Base de donnees** : SQLite
- **Serveur** : Gunicorn
- **Conteneurisation** : Docker
- **CI/CD** : GitHub Actions
- **Securite** : Gitleaks, TruffleHog, Flake8, Bandit, Semgrep, pip-audit, Trivy, Nikto
