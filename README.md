# little_agent — Gustave

**Un assistant IA capable de rechercher sur le Web, d'exécuter des commandes shell et de manipuler des fichiers depuis une interface de chat ou une API FastAPI.**

Le projet relie un agent `FunctionAgent` de LlamaIndex à un modèle hébergé par Ollama. À partir d'une demande en langage naturel, le modèle peut appeler les outils disponibles, exploiter leurs résultats et produire une réponse. Une mémoire distincte par session permet de poursuivre une conversation.

Le dépôt réunit le backend Python, une interface HTML/CSS/JavaScript sans étape de compilation, des tests unitaires, un Dockerfile et une chaîne GitHub Actions allant des contrôles de qualité au déclenchement du déploiement Render.

> L'application s'exécute sur votre machine ou dans un conteneur, mais l'inférence est distante : le client Ollama utilise actuellement `https://ollama.com`. Ce dépôt ne lance pas de serveur Ollama local.

## Fonctionnalités

- **Chat Web** servi par FastAPI, avec rendu Markdown des réponses, indicateur d'attente et bouton « Nouvelle session ».
- **API de conversation** : `POST /generate`, avec création ou réutilisation d'un identifiant de session.
- **Mémoire conversationnelle par session**, conservée côté serveur pendant la durée de vie du processus.
- **Six outils accessibles à l'agent** : recherche Web, extraction de pages, shell, lecture, écriture et édition de fichiers.
- **Traces d'utilisation des outils** dans la console du serveur : nom, arguments et résultat, limité à 1 000 caractères pour l'affichage du résultat.
- **Tests Pytest et lint Ruff**, puis construction et publication d'une image Docker avant l'appel d'un deploy hook Render.

Exemples de demandes à essayer :

- « Recherche la documentation officielle de FastAPI et résume les points utiles pour créer une route POST. »
- « Crée un fichier `notes/todo.txt` contenant une liste de tâches, puis relis-le. »
- « Remplace une phrase précise dans `notes/todo.txt`. »
- « Affiche la date et le répertoire courant avec le shell. »

Ces exemples sollicitent les outils existants ; leur exécution dépend du modèle choisi, des clés API et des permissions du processus.

## Architecture et stack

Un agent est construit au démarrage de FastAPI. Chaque requête récupère la mémoire associée à sa session, puis lance l'agent avec le message utilisateur. LlamaIndex orchestre les appels d'outils ; FastAPI renvoie la réponse finale et l'identifiant de session.

| Composant | Rôle | Fichiers |
| --- | --- | --- |
| FastAPI et Pydantic | Cycle de vie du serveur, validation JSON, routes et fichiers statiques | [app/main.py](app/main.py) |
| LlamaIndex Core | `FunctionAgent`, mémoire et traitement des événements d'exécution | [app/Agent.py](app/Agent.py) |
| Intégration Ollama | Inférence distante avec authentification Bearer | [app/Agent.py](app/Agent.py) |
| Tavily et subprocess | Recherche/extraction Web et exécution de commandes | [app/tools.py](app/tools.py) |
| pathlib et outils de fichiers | Lecture, création et remplacement de texte dans un espace de travail | [app/tools.py](app/tools.py) |
| HTML, CSS et JavaScript | Interface de chat et appels à `/generate` | [app/static/](app/static/) |
| Pytest et Ruff | Tests unitaires et lint | [tests/](tests/), [requirements.txt](requirements.txt) |
| Docker et GitHub Actions | Image Python et pipeline CI/CD vers Render | [Dockerfile](Dockerfile), [CICD.yml](.github/workflows/CICD.yml) |

**Python 3.11.9** est utilisé dans le Dockerfile et la CI. Les dépendances Python sont listées dans `requirements.txt` sans versions figées.

### Outils de l'agent

| Outil | Comportement implémenté |
| --- | --- |
| `web_search` | Recherche via Tavily ; profondeur, nombre de résultats, période et nombre d'extraits paramétrables. Par défaut : profondeur `basic`, 5 résultats. |
| `web_fetch` | Extraction du contenu d'une URL via Tavily, avec profondeur `basic` ou `advanced` et requête de pertinence optionnelle. |
| `shell` | Exécution non interactive ; Bash puis repli sur `sh` sur Linux/macOS, Git Bash sur Windows. Timeout de 30 secondes, sortie plafonnée à 5 000 caractères, statut et code de retour structurés. |
| `read_file` | Lecture de texte, UTF-8 par défaut ; sortie limitée à 5 000 caractères par défaut, plafond de 20 000 pour une limite positive. `None` ou une valeur négative désactive la troncature. |
| `write_file` | Création d'un fichier et de ses dossiers parents ; refuse de remplacer un fichier existant sauf si `overwrite=True`. |
| `edit_file` | Remplacement d'un fragment exact ; refuse une recherche vide, absente ou ambiguë. `allow_multiple=True` autorise le remplacement de toutes les occurrences. |

Les trois outils de fichiers résolvent les chemins dans `WORKSPACE_DIR` et refusent ceux qui sortent de cet espace. **Cette restriction ne s'applique pas au shell**, qui conserve les droits du processus et son répertoire de travail.

## Installation

### Prérequis

- Python 3.11.9 pour reproduire l'environnement de la CI.
- Git pour cloner le dépôt.
- Une clé Ollama et un modèle disponible sur le service distant, compatible avec les appels d'outils.
- Une clé Tavily pour utiliser les outils Web.
- Bash ou `sh` sur Linux/macOS ; **Git for Windows avec Git Bash** pour l'outil shell sur Windows.
- Docker uniquement pour le lancement en conteneur.

### Récupérer le projet et installer les dépendances

Depuis un terminal :

```bash
git clone https://github.com/gaviash/little_agent.git
cd little_agent
python -m venv .venv
```

Activer l'environnement sous Linux/macOS ou Git Bash :

```bash
source .venv/bin/activate
```

Sous Windows PowerShell :

```powershell
.\.venv\Scripts\Activate.ps1
```

Puis installer les dépendances :

```bash
python -m pip install -r requirements.txt
```

## Configuration

Créer un fichier `.env` à la racine du dépôt. Le code le charge depuis le répertoire courant lors de l'import de `app/tools.py`.

```dotenv
OLLAMA_API_KEY=remplacer_par_votre_cle_ollama
OLLAMA_MODEL=remplacer_par_le_nom_exact_du_modele_cloud
TAVILY_API_KEY=remplacer_par_votre_cle_tavily
WORKSPACE_DIR=./workspace
```

Ces valeurs sont des exemples à remplacer, pas des identifiants utilisables.

| Variable | Utilisation |
| --- | --- |
| `OLLAMA_API_KEY` | Clé envoyée au service Ollama dans l'en-tête `Authorization: Bearer …`. Nécessaire pour les conversations utilisant ce service. |
| `OLLAMA_MODEL` | Nom exact du modèle distant. Aucun modèle par défaut n'est défini dans le code. |
| `TAVILY_API_KEY` | Clé des outils Web. Le client est créé au premier appel Web ; si la clé manque, cet appel lève une erreur. |
| `WORKSPACE_DIR` | Racine des outils de fichiers. Facultative ; par défaut, le répertoire courant du processus. Un chemin relatif est résolu au démarrage. |
| `GIT_BASH_PATH` | Facultative sous Windows : chemin complet de `bash.exe` si la détection automatique de Git Bash échoue. |

Pour préparer l'espace de fichiers de l'exemple :

```bash
python -c "from pathlib import Path; Path('workspace').mkdir(exist_ok=True)"
```

Le fichier `.env` est exclu de Git et du contexte Docker. Le dossier `workspace/`, lui, n'est pas exclu par les fichiers d'ignore actuels : conserver les fichiers de travail et données privées hors des commits et du contexte de construction.

Les autres paramètres sont fixés dans [app/Agent.py](app/Agent.py) : URL Ollama `https://ollama.com`, température `0.2`, fenêtre de contexte demandée de `262144` tokens et timeout de requête de `100` secondes. La mémoire est configurée avec `token_limit=100000` dans [app/main.py](app/main.py). Ces valeurs sont des paramètres du client, pas une garantie de capacité du modèle. Il n'existe pas de variable permettant de modifier l'URL Ollama ; utiliser un serveur local nécessite une adaptation du code.

## Lancement et utilisation

### Serveur local

Lancer depuis la racine du dépôt pour que `.env` soit chargé au bon endroit :

```bash
fastapi dev app/main.py
```

Pour un lancement sans rechargement automatique, avec écoute sur les interfaces réseau :

```bash
fastapi run app/main.py --host 0.0.0.0 --port 8000
```

- Interface de chat : <http://127.0.0.1:8000/>
- Documentation interactive de l'API : <http://127.0.0.1:8000/docs>
- Ressources de l'interface : `/static`

Les commandes explicites ci-dessus sont à privilégier : les raccourcis `run` du Makefile et de `makefile.ps1` omettent le sous-ordre `dev` ou `run`, et `make install` référence `requirements` au lieu de `requirements.txt`.

### API `POST /generate`

Créer une conversation :

```bash
curl -X POST http://127.0.0.1:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"message":"Bonjour, peux-tu afficher la date actuelle ?"}'
```

La réponse JSON contient :

```json
{
  "response": "<réponse finale de l'agent>",
  "session_id": "<identifiant de session retourné>"
}
```

Pour poursuivre la conversation, transmettre l'identifiant reçu :

```bash
curl -X POST http://127.0.0.1:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"message":"Résume notre échange précédent.","session_id":"<identifiant reçu>"}'
```

`message` est obligatoire. Si `session_id` est absent, nul ou vide, le serveur crée un UUID ; un identifiant non vide encore inconnu crée une nouvelle mémoire.

L'interface conserve uniquement l'identifiant de session dans le `localStorage` du navigateur. Elle ne recharge pas l'historique visuel après un rafraîchissement. Le bouton « Nouvelle session » efface l'identifiant côté navigateur et les messages affichés ; il ne supprime pas l'ancienne mémoire côté serveur.

La route attend la réponse finale : les événements de l'agent sont traités côté serveur, mais le texte n'est pas diffusé progressivement au navigateur.

## Tests et qualité

Depuis la racine du dépôt, avec l'environnement Python activé :

```bash
python -m pytest tests -q
ruff check
```

Les raccourcis `make test` et `make lint` exécutent les mêmes contrôles. Sous PowerShell, utiliser `.\makefile.ps1 test` et `.\makefile.ps1 lint`.

| Suite | Comportements vérifiés |
| --- | --- |
| [test_agent.py](tests/test_agent.py) | Configuration du client Ollama, construction de l'agent avec ses six outils, transmission du message et de la mémoire. |
| [test_main.py](tests/test_main.py) | Création de session, réutilisation de mémoire et service des fichiers statiques. |
| [test_tools.py](tests/test_tools.py) | Création/lecture/édition de fichiers, refus d'écrasement ou de remplacement ambigu, troncature, refus des chemins externes, choix du shell, timeout et appel du client Tavily. |

Les appels à l'agent, à Ollama, à Tavily et aux sous-processus sont remplacés par des doubles dans les tests concernés. La suite ne valide donc pas les réponses d'un modèle réel ni un déploiement Render. Les modules de tests de l'agent et de l'API utilisent `pytest.importorskip` : vérifier les éventuels tests ignorés, pas seulement le code de sortie.

## Docker

Construire l'image depuis la racine :

```bash
docker build -t little-agent:local .
```

Lancer l'application avec les variables du fichier `.env` :

```bash
docker run --rm --env-file .env -p 8000:8000 little-agent:local
```

Le Dockerfile utilise `python:3.11.9-slim`, installe les dépendances Python et les utilitaires `curl`, `unzip`, `zip`, `procps`, `file` et `coreutils`, puis lance `fastapi run app/main.py` depuis `/prod`. Le port exposé est `8000`. L'image n'embarque ni modèle ni serveur Ollama.

Pour conserver les fichiers produits par les outils de fichiers sur l'hôte, monter un dossier dédié. Exemple sous Linux/macOS ou Bash compatible :

```bash
docker run --rm --env-file .env \
  -e WORKSPACE_DIR=/workspace \
  --mount "type=bind,source=$(pwd)/workspace,target=/workspace" \
  -p 8000:8000 little-agent:local
```

Créer au préalable le dossier `workspace`. Sans volume, les fichiers écrits dans le conteneur ne sont pas conservés après sa suppression. Le volume ne rend pas les mémoires de conversation persistantes.

## Déploiement et CI/CD

Le workflow [`.github/workflows/CICD.yml`](.github/workflows/CICD.yml) se déclenche sur un **push vers `master`** ou manuellement via `workflow_dispatch`. Aucun déclencheur `pull_request` n'est configuré.

Il exécute successivement :

1. Installation de Python 3.11.9 et des dépendances, puis `ruff check` et `pytest tests -q`.
2. Après réussite du job de tests, connexion à Docker Hub et construction/publication de l'image pour `linux/amd64`, avec cache GitHub Actions.
3. Appel HTTP POST du deploy hook Render.

| Secret GitHub Actions | Rôle |
| --- | --- |
| `DOCKERHUB_USERNAME` | Compte Docker Hub ; détermine le tag `<compte>/little-agent:latest`. |
| `DOCKERHUB_PASSWORD` | Identifiant secret utilisé pour la connexion à Docker Hub. |
| `RENDER_DEPLOY_HOOK_URL` | URL du deploy hook du service Render à déclencher après publication. |

Pour utiliser cette chaîne avec votre infrastructure :

1. Préparer le dépôt d'image Docker Hub et configurer les trois secrets GitHub Actions.
2. Créer/configurer un service Render utilisant l'image `<compte>/little-agent:latest` et reporter son deploy hook dans le secret correspondant.
3. Définir les variables d'environnement de l'application dans Render et rendre le port `8000` accessible selon la configuration du service.
4. Si les fichiers doivent persister, configurer le stockage et `WORKSPACE_DIR` côté hébergement.

Le dépôt fournit le Dockerfile et le workflow, mais aucun fichier de configuration Render. La commande du conteneur utilise le port par défaut de FastAPI ; elle ne lit pas explicitement une variable `PORT`. L'appel du hook déclenche le déploiement sans attendre ni vérifier que le service devient disponible.

## Limites et conditions d'exécution

- **Sessions en mémoire** : elles sont indexées dans `app.state.sessions`, sans sauvegarde au redémarrage ni mécanisme applicatif d'expiration. Elles ne sont pas partagées entre plusieurs processus serveur.
- **Accès à l'API** : aucune authentification n'est implémentée ; l'identifiant de session n'est pas une preuve d'identité.
- **Droits d'exécution** : le shell peut exécuter des commandes avec les droits du serveur et accéder aux chemins que ces droits autorisent. `WORKSPACE_DIR` protège uniquement les outils de fichiers ; les sessions partagent le même espace de travail et ne constituent pas une isolation.
- **Services externes** : les messages et résultats d'outils exploités par le modèle sont transmis à Ollama ; les requêtes Web passent par Tavily. Disponibilité, quotas et coûts dépendent de ces services.
- **Journalisation** : les arguments et résultats d'outils peuvent apparaître dans les logs du serveur.

Pour une utilisation exposée à d'autres utilisateurs, prévoir une authentification et un environnement d'exécution isolé avec des droits adaptés. Le conteneur fourni facilite le déploiement, mais ne constitue pas à lui seul une sandbox de sécurité.

## Licence

Aucun fichier de licence n'est présent dans le dépôt.
