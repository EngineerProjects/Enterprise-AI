# Skills — Procédures réutilisables injectées dans le contexte

Une **skill** est un fichier Markdown avec frontmatter YAML qui injecte des instructions procédurales dans le system prompt d'un agent. Les skills définissent *comment* faire une tâche (code review, debug systématique, brainstorming), pas *qui* est l'agent.

---

## Format d'un fichier skill

```markdown
---
name: code-review
description: "Revue de code pour la correction, la sécurité et le style."
when_to_use: "Quand on demande une revue de code ou avant un merge."
allowed-tools:
  - file_editor
  - code_search
model: claude-haiku-4-5-20251001   # optionnel : override du modèle
context: inline                     # inline | fork
---

# Revue de code

## Étape 1 — Compréhension
Lis d'abord l'ensemble du diff avant d'émettre le moindre commentaire.

## Étape 2 — Sécurité
Vérifie systématiquement :
- Injections SQL / XSS / commandes
- Gestion des erreurs et des cas limites
- Secrets hardcodés

## Étape 3 — Style
Respecte les conventions du projet existant.
```

### Champs frontmatter

| Champ | Type | Description |
|---|---|---|
| `name` | string | Identifiant de la skill (requis) |
| `description` | string | Résumé affiché dans les listings |
| `when_to_use` | string | Injecté comme commentaire HTML dans le prompt |
| `allowed-tools` | list | Restreint les outils disponibles quand la skill est active |
| `model` | string | Override du modèle pour cette skill |
| `context` | `inline` \| `fork` | `inline` = injecté dans le contexte courant |

---

## Utilisation

### Par nom (fichier .md dans le répertoire skills)

```python
agent = Agent(
    provider=provider,
    skills=["code-review", "systematic-debugging"],
)
```

### Par instance

```python
from enterprise_ai.skills import Skill

skill = Skill(
    name="my-procedure",
    description="Ma procédure custom",
    when_to_use="Pour les tâches X",
    body="## Étapes\n\n1. Fais ceci.\n2. Fais cela.",
)

agent = Agent(provider=provider, skills=[skill])
```

### Ajouter après construction

```python
agent.add_skill("code-review")
agent.add_skill(my_skill_instance)
```

---

## Preprocessing — variables et shell

### Substitution de variables `${var}`

Les placeholders `${var}` sont substitués avant injection :

```markdown
---
name: project-context
---
Agent ${agent_id} travaille sur le projet **${project}**.
Date : ${date}
Répertoire : ${pwd}
```

```python
agent = Agent(
    provider=provider,
    skills=["project-context"],
    skill_vars={
        "agent_id": "worker-1",
        "project": "myapp",
    },
)
# ${date} et ${pwd} sont injectés automatiquement
# ${agent_id} et ${project} viennent de skill_vars
```

Variables disponibles par défaut :

| Variable | Valeur |
|---|---|
| `${date}` | Date du jour ISO 8601 (`2026-06-02`) |
| `${pwd}` | Répertoire de travail courant |

Variables inconnues sont laissées telles quelles.

### Exécution de blocs shell (opt-in)

````markdown
---
name: git-context
---
Derniers commits :
```bash
git log --oneline -5
```

Branche courante :
```bash
git branch --show-current
```
````

```python
agent = Agent(
    provider=provider,
    skills=["git-context"],
    enable_shell_in_skills=True,   # désactivé par défaut
)
# Les blocs bash sont exécutés, leur stdout remplace le bloc
# Si la commande échoue ou produit du vide → bloc laissé intact
```

---

## SkillCurator — génération automatique de skills

Le `SkillCurator` analyse une session terminée et propose une skill réutilisable si le workflow suivi est générique et répétable.

```python
from enterprise_ai.skills.curator import SkillCurator

curator = SkillCurator(
    provider=provider,
    confidence_threshold=0.75,    # seuil de confiance (0-1)
    max_messages_to_sample=20,    # nb max de messages analysés
)

# Après une session réussie
result = await agent.run("Débogue l'erreur de segfault dans le module C")
proposal = await curator.analyze(agent.snapshot(), result)

if proposal:
    print(f"Skill proposée : {proposal.name} (confiance : {proposal.confidence:.0%})")
    print(proposal.body)

    # Sauvegarder en .md
    path = proposal.save("~/.enterprise-ai/skills/")
    print(f"Sauvegardée : {path}")

    # Injecter immédiatement dans l'agent
    agent.add_skill(proposal.to_skill())
```

### SkillProposal

```python
@dataclass
class SkillProposal:
    name: str              # kebab-case
    description: str
    when_to_use: str
    body: str              # Markdown
    confidence: float      # 0.0 – 1.0
    source_session_id: str

    def to_skill(self) -> Skill           # convertit en objet Skill live
    def to_markdown(self) -> str          # sérialise au format .md
    def save(self, directory) -> Path     # écrit le fichier .md
```

Le curator filtre les sessions :
- Trop spécifiques (noms de fichiers, repos, utilisateurs) → rejetées
- Faible confiance (< `confidence_threshold`) → rejetées
- Procédures généralisables avec étapes claires → proposées

---

## Skill.system_prompt_block()

Méthode bas niveau pour obtenir le bloc de texte injecté :

```python
skill = Skill(name="my-skill", body="Agent ${agent_id} prêt.", when_to_use="Toujours")

block = skill.system_prompt_block(
    vars={"agent_id": "worker-42"},
    enable_shell=False,
)
# <!-- Skill: my-skill | Toujours -->
# Agent worker-42 prêt.
```
