# Team & Mixture of Agents

---

## Team — coordination multi-agents

Une `Team` lance N agents en parallèle autour d'une **mission** commune. Les agents communiquent via une boîte mail partagée et un tableau de tâches, sans orchestrateur central. Chaque agent décide autonomement.

```python
from enterprise_ai import Agent, Team
from enterprise_ai.providers import AnthropicProvider

team = Team(
    agents=[
        Agent(
            provider=AnthropicProvider(),
            toolset="team_worker",
            system_prompt=(
                "Tu es le chef de projet. "
                "Décompose la mission en tâches et poste-les sur le board. "
                "Assigne-les via mail. Quand tout est terminé, appelle terminate."
            ),
        ),
        Agent(
            provider=AnthropicProvider(),
            toolset="team_worker",
            system_prompt=(
                "Tu es développeur backend. "
                "Prends les tâches de développement sur le board et implémente-les."
            ),
        ),
        Agent(
            provider=AnthropicProvider(),
            toolset="team_worker",
            system_prompt=(
                "Tu es testeur QA. "
                "Prends les tâches de test et écris les tests correspondants."
            ),
        ),
    ],
    mission_timeout=300.0,   # timeout global en secondes
)

result = await team.run("Implémente un module d'authentification JWT")

print(result.combined_output)    # sorties de tous les agents
print(result.task_summary)       # résumé du task board
print(result.outputs)            # dict agent_id → output
```

### Constructeur Team

| Paramètre | Type | Défaut | Description |
|---|---|---|---|
| `agents` | `list[Agent]` | requis | Agents participants |
| `mailbox` | `Mailbox \| None` | auto | Boîte mail partagée |
| `task_board` | `TaskBoard \| None` | auto | Tableau de tâches partagé |
| `memory` | `TeamMemory \| None` | `FTSMemory()` | Mémoire équipe partagée |
| `mission_timeout` | `float` | `300.0` | Timeout en secondes |
| `max_tokens_per_agent` | `int \| None` | `None` | Limite de tokens par agent |

### TeamResult

```python
class TeamResult:
    outputs: dict[str, str]     # agent_id → texte final
    task_summary: str           # résumé du task board

    @property
    def combined_output(self) -> str   # toutes les sorties concaténées
```

---

## Communication équipe

### Mailbox — messagerie entre agents

Les agents s'envoient des messages asynchrones :

```python
# Via les outils (le LLM utilise ces outils directement)
# send_mail(to="agent-id", subject="...", body="...")
# read_mail()  → lit les messages non lus
# mailbox_status()  → état de la boîte

# API directe (pour du code applicatif)
from enterprise_ai.team.mailbox import Mailbox

mailbox = Mailbox()
mailbox.register("agent-1")
mailbox.register("agent-2")

await mailbox.send(
    sender="agent-1",
    to="agent-2",
    subject="Revue de PR",
    body="La PR #42 est prête pour revue.",
)

messages = await mailbox.read("agent-2")
```

### TaskBoard — tâches partagées

```python
from enterprise_ai.team.task_board import TaskBoard

board = TaskBoard()

task_id = await board.post(
    title="Implémenter /api/users",
    description="Endpoint GET + POST pour les utilisateurs",
    posted_by="agent-manager",
)

# Un agent réclame la tâche
await board.claim(task_id, claimed_by="agent-dev")

# Marque comme terminée
await board.complete(task_id, result="Endpoint implémenté, tests passent.")

print(board.summary())   # résumé formaté de toutes les tâches
```

---

## Mixture of Agents (MoA)

Lance N agents **sur la même question** et agrège leurs réponses. Utile pour améliorer la fiabilité, obtenir plusieurs points de vue ou compenser les faiblesses d'un modèle par un autre.

```python
from enterprise_ai.agent.mixture import MixtureOfAgents, AggregationStrategy
from enterprise_ai.providers import AnthropicProvider, create_provider

moa = MixtureOfAgents(
    agents=[
        Agent(provider=AnthropicProvider(model="claude-opus-4-8")),
        Agent(provider=create_provider("openai", model="gpt-4o")),
        Agent(provider=AnthropicProvider(model="claude-haiku-4-5-20251001")),
    ],
    strategy=AggregationStrategy.synthesize,
)

result = await moa.run("Quelle est la meilleure architecture pour un système de cache distribué ?")
print(result.output)
print(f"Stratégie : {result.strategy}")
```

### Stratégies d'agrégation

| Stratégie | Comportement | `winner_index` |
|---|---|---|
| `synthesize` (défaut) | Agrégateur LLM fusionne les meilleures idées | `None` |
| `vote` | LLM juge choisit la meilleure réponse | index du gagnant |
| `best_of` | LLM note chaque réponse 1-10, retourne la meilleure | index du gagnant |

```python
# Stratégie vote
moa = MixtureOfAgents(agents=[...], strategy=AggregationStrategy.vote)
result = await moa.run("Quelle approche choisir ?")
print(f"Gagnant : agent {result.winner_index}")
print(result.output)   # réponse verbatim du gagnant

# Stratégie best_of avec agrégateur dédié
aggregator = Agent(provider=AnthropicProvider(model="claude-opus-4-8"))
moa = MixtureOfAgents(
    agents=[agent1, agent2, agent3],
    aggregator=aggregator,           # agent dont le provider fait l'agrégation
    strategy=AggregationStrategy.best_of,
)
```

### Constructeur MixtureOfAgents

| Paramètre | Type | Défaut | Description |
|---|---|---|---|
| `agents` | `list[Agent]` | requis | Au moins 1 agent |
| `aggregator` | `Agent \| None` | `agents[0]` | Agent dont le provider fait l'agrégation |
| `strategy` | `AggregationStrategy` | `synthesize` | Méthode d'agrégation |
| `timeout` | `float \| None` | `None` | Timeout sur la phase parallèle |

### MixtureResult

```python
@dataclass
class MixtureResult:
    output: str                         # réponse finale agrégée
    strategy: AggregationStrategy
    agent_results: list[SessionResult]  # réponse brute de chaque agent
    winner_index: int | None            # pour vote/best_of
    metadata: dict                      # données supplémentaires
```

### Gestion des erreurs

Un agent qui échoue (exception, timeout) produit un `SessionResult` avec `state=error` au lieu de faire crasher le MoA. Les autres agents continuent et l'agrégation s'effectue sur les réponses disponibles.

```python
result = await moa.run("question")
errors = [r for r in result.agent_results if r.state.value == "error"]
print(f"{len(errors)} agent(s) ont échoué sur {len(result.agent_results)}")
```

---

## Team vs MixtureOfAgents — quand utiliser quoi ?

| Critère | Team | MixtureOfAgents |
|---|---|---|
| Agents font des **tâches différentes** | ✓ | — |
| Agents répondent à la **même question** | — | ✓ |
| Communication inter-agents | ✓ (mail + tasks) | — |
| Améliorer la fiabilité d'une réponse | — | ✓ |
| Workflow avec rôles distincts | ✓ | — |
| Consensus / voting | — | ✓ |
