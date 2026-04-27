# Forum Brawlhalla - Application Flask securisee

Application web de forum dediee a la communaute **Brawlhalla**, developpee avec Flask et integrant une pipeline CI/CD securisee de A a Z avec GitHub Actions.

---

## Sommaire

1. [Presentation du site page par page](#1-presentation-du-site-page-par-page)
2. [Correctifs appliques suite a la phase de pentest](#2-correctifs-appliques-suite-a-la-phase-de-pentest)
3. [Pipeline CI/CD](#3-pipeline-cicd)
   - [3.1 Descriptif de la pipeline](#31-descriptif-de-la-pipeline)
   - [3.2 Erreurs les plus grosses rencontrees](#32-erreurs-les-plus-grosses-rencontrees)
   - [3.3 Correctifs apportes](#33-correctifs-apportes)

---

## 1. Presentation du site page par page

### Accueil (`/` - `index.html`)
Page d'accueil qui presente les differentes categories du forum. Affiche :
- Liste des categories avec icones et couleurs
- Statistiques globales : nombre total de topics, de posts et d'utilisateurs

### Categories (`/category/<id>` - `category.html`)
Page listant tous les sujets (topics) d'une categorie donnee. Fonctionnalites :
- Pagination des topics (15 par page)
- Acces rapide a la creation d'un nouveau topic
- **Cas particulier "Clips & Highlights"** : affiche en plus une galerie de videos (clips de gameplay) avec un formulaire d'upload video
- **Cas particulier "Actualites & Patchs"** : seuls les admins peuvent y creer des topics

### Sujet / Topic (`/topic/<id>` - `topic.html`)
Page de detail d'un sujet avec son fil de discussion. Fonctionnalites :
- Affichage du contenu initial et des reponses (paginees, 20 par page)
- Formulaire de reponse (utilisateurs connectes uniquement)
- Filtre de censure automatique (`censor_text`) sur le contenu poste
- Suppression de son propre topic / ses propres posts

### Inscription (`/register` - `register.html`)
Formulaire d'inscription avec :
- Validation du username, email et mot de passe (via `Flask-WTF`)
- Verification de l'unicite du username/email
- Hashage du mot de passe via **PBKDF2-SHA256 / 600 000 iterations** (`werkzeug.security`)
- Generation d'une couleur d'avatar aleatoire

### Connexion (`/login` - `login.html`)
Formulaire de connexion classique. Message d'erreur generique (ne distingue pas username inconnu de mot de passe faux).

### Deconnexion (`/logout`)
Route qui detruit la session utilisateur.

### Profil (`/profile/<username>` - `profile.html`)
Page de profil publique d'un utilisateur affichant :
- Avatar (upload ou couleur generee)
- Les 5 derniers topics crees
- Les 5 dernieres reponses postees

### Changement de mot de passe (`/change-password` - `change_password.html`)
Fonctionnalite securisee avec :
- Rate limiting : **5 tentatives maximum par tranche de 15 minutes**
- Verification de l'ancien mot de passe
- Refus si le nouveau mot de passe est identique a l'ancien
- Invalidation totale de la session apres changement (force la reconnexion)

### Upload d'avatar (`/upload-avatar` - `upload_avatar.html`)
Page permettant a l'utilisateur de changer son avatar. **7 couches de verification** (voir section 2).

### Tier List (`/tier-list` - `tier_list.html`)
Page statique presentant le classement des **legendes Brawlhalla** par tier (S, A, B, C, D).

### True Combos (`/true-combos` - `true_combos.html`)
Page statique listant les vrais combos (combos garantis) pour chaque legende.

### Chat en direct (`/chat` - `chat.html`)
Chat communautaire en temps reel accessible aux utilisateurs connectes.
- API REST : `GET /api/chat/messages` renvoie les 50 derniers messages
- `POST /api/chat/messages` pour envoyer un message
- Filtre de censure applique a chaque message

### Clips & Highlights (upload video)
Gere via la page `category.html` pour la categorie "Clips & Highlights". Permet l'upload de videos (mp4, webm, mov, avi) avec les memes couches de securite que l'avatar (adaptees aux formats video).

---

## 2. Correctifs appliques suite a la phase de pentest

Le pentest a identifie plusieurs vulnerabilites qui ont ete corrigees :

### Upload de fichiers (avatar & videos) - Defense en profondeur

**Vulnerabilites initiales** : upload de fichiers polyglotes (shell PHP cache dans une image), double extensions (`shell.php.jpg`), path traversal, RCE via fichier malveillant.

**Correctifs (7 couches appliquees dans `app.py`)** :

1. **Whitelist stricte d'extensions** : seules `.jpg`, `.png`, `.gif` sont autorisees (videos : `.mp4`, `.webm`, `.mov`, `.avi`)
2. **Blocage des doubles extensions** : rejet systematique des fichiers type `shell.php.jpg`
3. **Detection du Content-Type cote serveur** : ignore le `Content-Type` envoye par le client, detecte le vrai type via les magic bytes
4. **Verification des magic bytes** : controle des premiers octets du fichier
5. **Validation coherence extension/contenu** : l'extension declaree doit correspondre au type reel detecte
6. **Scan de code malveillant** : detection des patterns `<?php`, `<script`, `eval(`, `exec(`, `import os`, etc.
7. **Re-encodage via Pillow** : l'image est ouverte puis reenregistree, ce qui supprime tout payload cache (metadonnees EXIF, chunks malveillants, polyglots)
8. **Nom de fichier aleatoire (UUID)** : evite la reecriture de fichiers existants et la prediction de noms
9. **Limite de taille** : 2 Mo pour les avatars, 50 Mo pour les videos
10. **Path traversal** : `os.path.basename()` applique dans la route de service des fichiers

### Authentification

**Vulnerabilites initiales** : brute force du changement de mot de passe, session persistante apres changement de mot de passe.

**Correctifs** :
- **Rate limiting** : 5 tentatives / 15 min sur `/change-password`
- **Invalidation de session** : `logout_user()` + `session.clear()` apres changement de mot de passe
- **Hashage fort** : PBKDF2-SHA256 avec **600 000 iterations** (au lieu du default 260k)
- **Refus du meme mot de passe** : le nouveau doit etre different de l'ancien

### Protection contre XSS / CSRF / Clickjacking

**Correctifs** (`app.py` + `config.py`) :
- **Flask-Talisman** : headers HTTP de securite + Content Security Policy stricte
- **Flask-WTF CSRF Protection** : tous les formulaires sont proteges
- **Cookies securises** :
  - `SESSION_COOKIE_SECURE = True` (HTTPS only)
  - `SESSION_COOKIE_HTTPONLY = True` (bloque l'acces JS)
  - `SESSION_COOKIE_SAMESITE = 'Lax'` (anti-CSRF)
- **`WTF_CSRF_SSL_STRICT = True`** : referrer strict HTTPS

### Autres corrections

- **Authorization checks** : verification `user_id == current_user.id` sur les suppressions de topics/posts
- **Admin only** sur la creation de topics "Actualites & Patchs"
- **Censure de contenu** : `censor_text()` applique sur tous les inputs utilisateur (topics, posts, chat)
- **Limitation de la taille des requetes** : `MAX_CONTENT_LENGTH = 50 Mo`
- **Messages d'erreur generiques** a la connexion (pas de leak sur l'existence d'un username)

---

## 3. Pipeline CI/CD

### 3.1 Descriptif de la pipeline

La pipeline est definie dans `.github/workflows/pipeline.yml` et se declenche sur `push` / `pull_request` vers les branches `dev` et `main`.

#### Schema d'execution

```
push / PR sur dev ou main
        |
   +---------+
   | changes |  --> Detecte si des fichiers Python/Docker ont change (dorny/paths-filter)
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
                    trivy-fs (scan filesystem pre-build)
                         |
                  docker-build-scan (build + Trivy image post-build)
                         |
                  dast-wapiti (docker-compose up + Wapiti)
                         |
                  docker-push (deploy DockerHub)
                    [main only]
```

#### Couverture par Lab

| Lab | Objectif | Outils / Features |
|-----|----------|-------------------|
| **Lab 1** - Qualite & Secrets | Lint + detection de secrets | Flake8, Gitleaks (+ regle custom `vc_*`), TruffleHog |
| **Lab 2** - SAST & SCA | Vulnerabilites code + dependances | Bandit, Semgrep (+ **6 regles custom policy-as-code**), pip-audit |
| **Lab 3** - Docker & Image Security | Image Docker securisee | Trivy pre-build (filesystem) + Trivy post-build (image) |
| **Lab 4** - DAST & Deploy | Test runtime + deploy | **docker-compose** pour demarrer l'app, **Wapiti** pour le scan DAST, push DockerHub |
| **Lab 5** - CI/CD intelligente | Execution conditionnelle | `paths-filter` (changements Python uniquement), `needs` pour parallelisation, `actions/cache` |

#### Regles custom Semgrep (`.semgrep/custom-rules.yml`)
Policy-as-code implementee :
- `no-debug-true` : interdit `debug=True`
- `no-md5-usage` : interdit `hashlib.md5()`
- `no-hardcoded-secret-key` : interdit les `SECRET_KEY` en dur
- `no-shell-true-subprocess` : interdit `shell=True`
- `no-eval` / `no-exec` : interdit `eval()` et `exec()`

#### Artefacts generes
Chaque execution produit les rapports suivants, telechargeables depuis l'onglet GitHub Actions :

| Artefact | Format | Contenu |
|----------|--------|---------|
| `bandit-report` | JSON | Analyse SAST Bandit |
| `semgrep-reports` | JSON | Semgrep (regles par defaut + custom) |
| `trivy-fs-report` | TXT | Scan Trivy filesystem (pre-build) |
| `trivy-image-report` | TXT | Scan Trivy image Docker (post-build) |
| `wapiti-report` | HTML | Scan DAST Wapiti |

### 3.2 Erreurs les plus grosses rencontrees

Au cours de la construction de la pipeline, plusieurs blocages majeurs ont ete rencontres :

#### Erreur 1 : Semgrep cassait la pipeline
Semgrep avait ete ajoute mais plantait systematiquement, ce qui a conduit a le commenter entierement. Resultat : la pipeline etait "verte" mais Semgrep n'etait plus execute du tout, perdant l'interet du SAST complementaire. [👉 Voir le correctif](#correctif-1--semgrep-re-active-et-isole)

#### Erreur 2 : Rapport Nikto vide / artefact manquant
Le scan Nikto original utilisait `docker cp $(docker ps -lq):/tmp/nikto-report.html` pour recuperer le rapport. Mais le conteneur etait deja arrete au moment de la commande, donc **l'artefact etait systematiquement vide**. [👉 Voir le correctif](#correctif-2--wapiti-via-docker-compose)

#### Erreur 3 : Trivy bloquait toute la pipeline
Avec `exit-code: '1'` et `severity: HIGH,CRITICAL`, Trivy faisait echouer l'ensemble de la pipeline au premier CVE trouve dans une dependance transitive, empechant d'atteindre le job DAST et le deploy. [👉 Voir le correctif](#correctif-3--trivy-non-bloquant)

#### Erreur 4 : Jobs executes inutilement
Tous les jobs tournaient sur chaque push (meme les modifications de README). Aucune dependance conditionnelle, **gaspillage de minutes CI/CD**. [👉 Voir le correctif](#correctif-4--cicd-intelligente-lab-5)

#### Erreur 5 : Docker build echoue a cause des BuildKit secrets
Le `Dockerfile` utilise `--mount=type=secret,id=ctf_flag` et plusieurs autres secrets. Sans passer ces secrets au `docker build` dans le CI, le build echouait immediatement avec une erreur cryptique. [👉 Voir le correctif](#correctif-5--gestion-des-buildkit-secrets-en-ci)

#### Erreur 6 : Gitleaks detectait de faux positifs
Le fichier `gitleaks.toml` contenait une regle custom qui matchait trop de choses, bloquant la pipeline sur des chaines legitimes (noms de variables, exemples dans les commentaires). [👉 Voir le correctif](#correctif-6--regle-gitleaks-affinee)

#### Erreur 7 : DockerHub push tentait de tourner sur `dev`
Le job `docker-push` essayait de se connecter a DockerHub sur chaque push de branche `dev`, alors que les secrets DockerHub ne sont supposes etre utilises qu'en production (`main`). [👉 Voir le correctif](#correctif-7--docker-push-conditionne-a-main)

##### Erreur 8 : Gérer Docker Swarm automatiquement
Etant donnné le contexte du projet nous avons été contraint de ne plus utiliser Render. En effet le free tier de Render ne permet plus l'accès SSH ni le déploiement via Docker Swarm. L'implémentation d'un Worker avec une VM était également trop compliqué avec le peu de temps qu'il nous restait.

### 3.3 Correctifs apportes

#### Correctif 1 : Semgrep re-active et isole
- Passage de l'action `returntocorp/semgrep-action` a une installation pip directe
- Separation des regles `auto` et `.semgrep/custom-rules.yml` en deux scans distincts
- Les rapports sont uploadees en artefact (`semgrep-reports`)

#### Correctif 2 : Wapiti via docker-compose
- **Nikto supprime**, remplace par **Wapiti** (image `cyberwatch/wapiti:latest`)
- Creation d'un `docker-compose.yml` avec healthcheck
- Lancement de l'app via `docker compose up -d --build`
- **Rapport monte via volume** (`-v "${{ github.workspace }}/reports:/reports"`) au lieu de `docker cp` → le fichier persiste meme apres l'arret du conteneur
- `docker compose down -v` en cleanup (avec `if: always()`)

#### Correctif 3 : Trivy non bloquant
- `exit-code: '0'` : Trivy affiche les vulnerabilites mais ne bloque plus la pipeline
- Les rapports sont toujours uploades en artefact pour revue manuelle
- Separation en 2 jobs : `trivy-fs` (pre-build) et `docker-build-scan` (post-build) pour isoler les problemes

#### Correctif 4 : CI/CD intelligente (Lab 5)
Introduction d'un job `changes` avec `dorny/paths-filter@v3` :
```yaml
filters: |
  python:
    - '**/*.py'
    - 'requirements.txt'
  docker:
    - 'Dockerfile'
    - 'requirements.txt'
    - '.dockerignore'
```
Les jobs `lint`, `sast-bandit`, `sast-semgrep` et `sca` utilisent `if: needs.changes.outputs.python == 'true'` pour ne s'executer que si necessaire. Ajout de `actions/cache@v4` pour le cache pip.

#### Correctif 5 : Gestion des BuildKit secrets en CI
Les secrets sont injectes via process substitution dans le job `docker-build-scan` :
```yaml
docker build \
  --secret id=ctf_flag,src=<(echo "FLAG{test_ci_cd}") \
  --secret id=db_password,src=<(echo "ci_test_password") \
  --secret id=api_key,src=<(echo "ci_test_api_key") \
  -t app-securisee:${{ github.sha }} .
```
En production (`docker-push`), ces valeurs sont tirees des vrais secrets GitHub (`${{ secrets.CTF_FLAG }}`, etc.).

#### Correctif 6 : Regle Gitleaks affinee
La regle custom dans `gitleaks.toml` a ete recentree sur le pattern strict :
```toml
regex = '''(?i)(mdp|password|token|key)\s*[:=]\s*["']?(vc_[A-Za-z0-9]{8,20})["']?'''
secretGroup = 2
```
Elle ne matche plus que les vrais secrets au format `vc_XXXX` precedes d'un mot-cle.

#### Correctif 7 : `docker-push` conditionne a `main`
```yaml
if: github.ref == 'refs/heads/main' && github.event_name == 'push'
```
Le job DockerHub ne tourne plus que sur les push vers `main`, jamais sur les PR ou les branches de dev.

---

## Configuration requise

### Secrets GitHub
A configurer dans **Settings > Secrets and variables > Actions** :

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

Ou via docker-compose :
```bash
export CTF_FLAG="FLAG{dev}"
export DB_PASSWORD="dev_password"
export API_KEY="dev_api_key"
docker compose up --build
```
##### Correction 8
Nous avons mis en place un self-hosted runner GitHub Actions sur notre machine locale. Cela permet à la pipeline de piloter Swarm automatiquement à chaque git push. Nous avons du installer un agent github puis configurer le pipeline.yml afin de piloter Docker Swarm.

## Stack technique

- **Backend** : Flask 3.1, Flask-SQLAlchemy, Flask-Login, Flask-WTF, Flask-Talisman
- **Base de donnees** : SQLite
- **Serveur** : Gunicorn
- **Conteneurisation** : Docker + docker-compose
- **CI/CD** : GitHub Actions
- **Securite** : Gitleaks, TruffleHog, Flake8, Bandit, Semgrep, pip-audit, Trivy, Wapiti


## Difficulté deploiement 

- Lint flake8 : config.py pb de syntaxe ( espace ect)
