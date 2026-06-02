# Contribuer à enterprise-ai

Merci de l'intérêt que tu portes au projet. Ce guide couvre tout ce qu'il faut savoir pour contribuer efficacement.

---

## Table des matières

1. [Code de conduite](#1-code-de-conduite)
2. [Comment contribuer](#2-comment-contribuer)
3. [Mise en place de l'environnement](#3-mise-en-place-de-lenvironnement)
4. [Workflow Git](#4-workflow-git)
5. [Standards de code](#5-standards-de-code)
6. [Tests](#6-tests)
7. [Structure du projet](#7-structure-du-projet)
8. [Règles de dépendances](#8-règles-de-dépendances)
9. [Messages de commit](#9-messages-de-commit)
10. [Ouvrir une Pull Request](#10-ouvrir-une-pull-request)
11. [Signaler un bug](#11-signaler-un-bug)
12. [Proposer une fonctionnalité](#12-proposer-une-fonctionnalité)

---

## 1. Code de conduite

Ce projet applique un code de conduite simple : **respect et professionnalisme**.

- Critique le code, jamais la personne
- Les questions débutantes sont les bienvenues
- Les discussions techniques restent factuelles
- Toute forme de harcèlement entraîne une exclusion immédiate

---

## 2. Comment contribuer

### Ce qu'on accepte volontiers

- Corrections de bugs avec test de non-régression
- Nouveaux providers LLM (OpenAI-compatible ou natif)
- Nouveaux outils builtin (`enterprise_ai/tools/builtin/`)
- Amélioration de la documentation
- Amélioration des messages d'erreur
- Optimisations de performance mesurables

### Ce qui nécessite une discussion préalable

- Nouvelles fonctionnalités majeures → ouvre une issue d'abord
- Changements d'API publique → discussion obligatoire
- Nouvelles dépendances core → justification requise

### Ce qu'on n'accepte pas

- Code sans tests
- Dépendances non épinglées dans `pyproject.toml`
- Breaking changes sans migration path
- Code qui baisse la couverture de tests existants

---

## 3. Mise en place de l'environnement

### Prérequis

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (gestionnaire de paquets)

### Installation

```bash
git clone https://github.com/ton-org/enterprise-ai.git
cd enterprise-ai

# Créer l'environnement et installer toutes les dépendances de dev
make setup_uv

# Vérifier que tout fonctionne
make test
```

### Variables d'environnement

Copie `.env.example` si disponible, sinon exporte au minimum :

```bash
export ANTHROPIC_API_KEY="sk-ant-..."   # pour les tests d'intégration
```

Les tests unitaires n'ont pas besoin de clé API (tout est mocké).

---

## 4. Workflow Git

### Branches

| Branche | Rôle |
|---|---|
| `main` | Code stable, releases uniquement |
| `dev` | Branche de développement principale — les PRs ciblent ici |

### Créer une branche de travail

```bash
git checkout dev
git pull origin dev
git checkout -b feat/mon-nouveau-truc
# ou
git checkout -b fix/description-du-bug
git checkout -b docs/ce-qui-change
```

### Conventions de nommage

```
feat/nom-court          nouvelle fonctionnalité
fix/nom-court           correction de bug
docs/nom-court          documentation uniquement
refactor/nom-court      refactoring sans changement fonctionnel
chore/nom-court         maintenance (deps, CI, config)
test/nom-court          ajout ou correction de tests
```

---

## 5. Standards de code

### Formatage et lint

```bash
make format    # ruff format + ruff check --fix
make lint      # ruff check + mypy
```

Tout le code doit passer sans erreur avant d'ouvrir une PR.

### Règles clés

**Typage — obligatoire**

Tout le code source dans `enterprise_ai/` doit être annoté. mypy ne doit rapporter aucune erreur.

```python
# Bien
async def complete(self, messages: list[Message], tools: list[ToolSchema] | None = None) -> LLMResponse:

# Mal
async def complete(self, messages, tools=None):
```

**Commentaires — minimaliste**

Ne commente que ce qui n'est pas évident depuis le code lui-même. Pas de docstrings multi-paragraphes, pas de commentaires qui répètent ce que le nom de la variable dit.

```python
# Bien — explique un invariant non-évident
# Rotation sans délai : la boucle de retry ne voit qu'un seul 429 par pool complet
if getattr(exc, "status_code", None) == 429 and not self._pool.rotate():
    continue

# Mal — répète ce que le code dit déjà
# Iterate over the list of messages and add each one to memory
for msg in messages:
    self._memory.add(msg)
```

**Pas de sur-ingénierie**

- Trois lignes similaires valent mieux qu'une abstraction prématurée
- Ne pas ajouter de paramètres "pour le futur"
- Ne pas créer de fichiers helper pour une seule fonction

**Gestion des erreurs**

- Valider uniquement aux frontières du système (input utilisateur, API externe)
- Faire confiance aux garanties internes du framework
- Ne pas capturer `Exception` sauf cas documenté

**Imports**

- Imports stdlib, puis tiers, puis projet — séparés par une ligne vide
- Imports locaux différés dans les fonctions pour éviter les cycles

```python
from __future__ import annotations  # toujours en premier

import asyncio                       # stdlib
from typing import Any

import httpx                         # tiers

from enterprise_ai.schema import Message  # projet
```

**Async**

- Tout I/O doit être `async`
- Jamais de `time.sleep()` dans du code async — utiliser `asyncio.sleep()`
- Les générateurs async doivent avoir `yield` même s'ils ne yielden jamais (pour satisfaire mypy)

---

## 6. Tests

### Lancer les tests

```bash
make test                                      # tous les tests
uv run pytest tests/test_mon_module.py -v      # un fichier
uv run pytest -k "test_ma_fonction" -v        # un test précis
uv run pytest --cov=enterprise_ai             # avec couverture
```

### Règles pour les tests

**Chaque PR doit inclure des tests.** Pas de code sans test, pas d'exception.

**Structure d'un fichier de test**

```python
"""Tests pour MonModule — description courte."""
from __future__ import annotations

import pytest
from enterprise_ai.mon_module import MaClasse


# ── Section 1 — Comportement de base ────────────────────────────────────────

def test_cas_normal():
    obj = MaClasse(param="valeur")
    assert obj.result == "attendu"


def test_cas_limite():
    ...


# ── Section 2 — Comportement async ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_async_flow():
    ...
```

**Mocking**

- Mocker les appels API LLM avec `Provider` fake (voir exemples dans `tests/`)
- Ne jamais faire d'appel réseau réel dans les tests unitaires
- Utiliser `unittest.mock.patch` pour les dépendances externes

**Fake Provider pattern** (standard du projet)

```python
from typing import AsyncIterator
from enterprise_ai.providers.base import LLMResponse, Provider
from enterprise_ai.schema import StreamEvent

class FakeProvider(Provider):
    @property
    def model(self) -> str:
        return "fake"

    async def complete(self, messages, tools=None, max_tokens=8096, **kwargs):
        return LLMResponse(content="réponse simulée", tool_calls=[])

    async def stream(self, *a, **kw) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError
        yield  # rend la fonction async generator pour mypy
```

**Couverture**

La couverture globale ne doit pas baisser. Pour chaque nouveau module, viser > 80%.

```bash
uv run pytest --cov=enterprise_ai --cov-report=html
# Ouvre htmlcov/index.html
```

---

## 7. Structure du projet

```
enterprise_ai/
├── agent/          # Agent, MixtureOfAgents
├── engine/         # QueryLoop, StopHooks, TokenBudget
├── execution/      # Orchestrator, StreamingExecutor
├── hooks/          # HookRegistry, HookExecutor, HookEvent
├── mcp/            # MCPManager, MCPClient, configs
├── memory/         # SessionMemory, LongTermMemory, ContextEngine
├── modes/          # ExecutionMode
├── permissions/    # PermissionEngine
├── prompt/         # PromptBuilder, cache helpers, templates
├── providers/      # AnthropicProvider, OpenAIProvider, retry, errors
├── sandbox/        # LocalSandbox, DockerSandbox
├── schema/         # Message, ToolCall, StreamEvent, SessionResult
├── skills/         # Skill, SkillCurator, preprocessing
├── stream/         # StreamScrubber, TagScrubber
├── team/           # Team, Mailbox, TaskBoard
└── tools/
    ├── builtin/    # BashTool, FileEditorTool, WebSearchTool, …
    ├── contract.py # BaseTool ABC
    ├── registry.py
    ├── toolsets.py
    └── search_bridge.py
```

### Où ajouter un outil builtin

1. Créer `enterprise_ai/tools/builtin/mon_outil.py`
2. L'exporter dans `enterprise_ai/tools/builtin/__init__.py`
3. L'enregistrer dans `_builtin_factories()` dans `toolsets.py` si applicable
4. Créer `tests/test_mon_outil.py`

### Où ajouter un provider

1. Créer `enterprise_ai/providers/mon_provider.py` — implémenter `Provider`
2. L'enregistrer dans `enterprise_ai/providers/factory.py` (si applicable)
3. L'exporter dans `enterprise_ai/providers/__init__.py`
4. Ajouter les dépendances dans `pyproject.toml` (extras si non-core)

---

## 8. Règles de dépendances

### Dépendances core (dans `dependencies`)

Uniquement les paquets nécessaires à **chaque session agent**. Elles sont épinglées à la version exacte (`==X.Y.Z`).

```toml
# Bien
"anthropic==0.49.0"

# Mal
"anthropic>=0.49.0"
"anthropic"
```

### Dépendances extras

Les providers, backends de recherche, sandboxes → dans `[project.optional-dependencies]`.

### Ajouter une dépendance

1. Justifie pourquoi elle est nécessaire (ne pas ajouter pour une seule utilisation)
2. Vérifie qu'elle est activement maintenue
3. Épingle la version exacte
4. Régénère le lock file : `uv lock`
5. Documente l'extra dans `pyproject.toml` et dans `docs/quickstart.md`

### Imports différés pour les extras

Si une dépendance est optionnelle, importe-la à l'intérieur de la fonction avec un message d'erreur clair :

```python
def _get_qdrant_client(self):
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        raise ImportError(
            "qdrant-client est requis pour VectorMemory avec le backend Qdrant. "
            "Installe-le avec : pip install 'enterprise-ai[qdrant]'"
        )
    return QdrantClient(...)
```

---

## 9. Messages de commit

Format : `type: description courte en français ou anglais`

### Types valides

| Type | Quand |
|---|---|
| `feat` | Nouvelle fonctionnalité |
| `fix` | Correction de bug |
| `docs` | Documentation uniquement |
| `refactor` | Refactoring sans changement fonctionnel |
| `test` | Ajout ou correction de tests |
| `chore` | Maintenance (deps, CI, config, build) |
| `perf` | Amélioration de performance |

### Règles

```bash
# Bien
feat: add SkillCurator for post-session skill extraction
fix: TagScrubber handles tags split across chunk boundaries
docs: document MixtureOfAgents aggregation strategies

# Mal
fix stuff
WIP
update code
feat: Add a new super cool feature that does many things and also fixes bugs
```

- Ligne de titre : max 72 caractères
- Temps présent, mode impératif ("add", pas "added" ou "adds")
- Corps optionnel pour expliquer le *pourquoi* (pas le *quoi*)

---

## 10. Ouvrir une Pull Request

### Avant d'ouvrir

```bash
# S'assurer que tout passe
make lint    # ruff + mypy : 0 erreur
make test    # tous les tests verts
```

### Checklist PR

- [ ] Tests ajoutés pour chaque nouveau comportement
- [ ] `make lint` passe sans erreur
- [ ] `make test` passe sans erreur
- [ ] La couverture n'a pas baissé
- [ ] La documentation est à jour si l'API publique change
- [ ] Le titre de la PR suit le format `type: description`
- [ ] La branche cible est `dev` (jamais `main` directement)

### Template de description

```markdown
## Contexte

Brève description du problème ou de la feature.

## Changements

- Ce qui a été ajouté/modifié/supprimé
- ...

## Tests

Décrire les tests ajoutés et comment les lancer.

## Notes pour la review

Mentionner les points d'attention particuliers.
```

### Review process

- Au moins 1 approbation requise avant merge
- Les commentaires de review doivent être adressés (résolus ou discutés)
- Les PRs ouvertes depuis plus de 30 jours sans activité sont fermées

---

## 11. Signaler un bug

Ouvre une issue avec le template suivant :

```markdown
**Version** : enterprise-ai X.Y.Z
**Python** : 3.11 / 3.12 / 3.13
**OS** : Linux / macOS / Windows

**Description**
Ce qui se passe vs ce qui devrait se passer.

**Reproduction minimale**
```python
# Code minimal qui reproduit le bug
```

**Traceback**
```
Coller la stack trace complète ici
```

**Contexte additionnel**
Tout ce qui peut aider.
```

---

## 12. Proposer une fonctionnalité

Ouvre une issue avec :

1. **Le problème** : quel besoin n'est pas couvert actuellement ?
2. **La solution proposée** : comment tu envisages de l'implémenter
3. **Les alternatives** : d'autres approches envisagées et pourquoi tu les rejettes
4. **L'impact** : qui en bénéficie, est-ce que ça casse quelque chose

Les features majeures sont discutées **avant** que du code soit écrit. Ouvre l'issue d'abord, code ensuite.

---

## Questions ?

- Ouvre une issue avec le label `question`
- Consulte la [documentation](docs/README.md) en premier
