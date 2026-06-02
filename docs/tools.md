# Tools — Outils intégrés, custom et toolsets

---

## Outils intégrés

| Classe | Nom LLM | Description |
|---|---|---|
| `BashTool` | `bash` | Exécute des commandes shell |
| `FileEditorTool` | `file_editor` | Lit, édite et écrit des fichiers |
| `CodeSearchTool` | `code_search` | Recherche dans la codebase (grep/ripgrep) |
| `WebSearchTool` | `web_search` | Recherche web (DuckDuckGo, Exa, Tavily, Firecrawl) |
| `TerminateTool` | `terminate` | Termine explicitement la session |
| `SpawnTool` | `spawn_agent` | Crée un sous-agent pour déléguer une tâche |

### Outils équipe

| Classe | Nom LLM | Description |
|---|---|---|
| `SendMailTool` | `send_mail` | Envoie un message à un autre agent |
| `ReadMailTool` | `read_mail` | Lit la boîte de réception |
| `MailboxStatusTool` | `mailbox_status` | Vérifie l'état de la boîte |
| `PostTaskTool` | `post_task` | Poste une tâche sur le task board |
| `ClaimTaskTool` | `claim_task` | Réclame une tâche disponible |
| `CompleteTaskTool` | `complete_task` | Marque une tâche comme terminée |
| `FailTaskTool` | `fail_task` | Marque une tâche comme échouée |
| `ListTasksTool` | `list_tasks` | Liste les tâches du board |

### Outils mémoire (auto-injectés avec `long_term_memory`)

| Classe | Nom LLM | Description |
|---|---|---|
| `RememberTool` | `remember` | Écrit un souvenir persistant |
| `RecallTool` | `recall` | Recherche dans la mémoire longue |
| `ForgetTool` | `forget` | Supprime un souvenir par ID |
| `RecentMemoriesTool` | `recent_memories` | Récupère les souvenirs récents |

---

## Importer les outils

```python
from enterprise_ai.tools.builtin import (
    BashTool,
    FileEditorTool,
    CodeSearchTool,
    WebSearchTool,
    TerminateTool,
    SpawnTool,
)

agent = Agent(
    provider=provider,
    tools=[BashTool(), FileEditorTool(), CodeSearchTool()],
)
```

---

## Toolsets — groupes prédéfinis

Au lieu de lister les outils, utilise un toolset :

```python
agent = Agent(provider=provider, toolset="development")
```

| Toolset | Contenu |
|---|---|
| `minimal` | `bash`, `file_editor`, `terminate` |
| `development` | `bash`, `file_editor`, `code_search`, `terminate` |
| `research` | `web_search`, `code_search`, `terminate` |
| `full` | Tous les outils standalone |
| `team_worker` | `development` + tous les outils équipe |

Combiner un toolset avec des outils custom (les outils explicites ont la priorité) :

```python
agent = Agent(
    provider=provider,
    toolset="development",
    tools=[MyCustomTool()],   # s'ajoute au toolset
)
```

### Toolset custom

```python
from enterprise_ai.tools.toolsets import register_toolset, register_tool_factory

# Enregistre la factory de ton outil
register_tool_factory("my_db", lambda: MyDatabaseTool())

# Crée un toolset qui l'inclut
register_toolset("backend", {
    "description": "Stack backend complet",
    "tools": ["bash", "file_editor", "my_db"],
    "includes": ["development"],   # inclut récursivement
})

agent = Agent(provider=provider, toolset="backend")
```

Lister les toolsets disponibles :

```python
from enterprise_ai.tools.toolsets import list_toolsets
print(list_toolsets())
# {'minimal': 'Bash + file editor + terminate', 'development': '...', ...}
```

---

## Créer un outil custom

```python
from pydantic import BaseModel
from enterprise_ai.tools.contract import BaseTool
from enterprise_ai.tools.context import ToolContext
from enterprise_ai.schema import ToolResult


class SearchInput(BaseModel):
    query: str
    max_results: int = 10


class MySearchTool(BaseTool):
    name = "my_search"
    description = "Recherche dans notre base de données interne"
    input_schema = SearchInput

    async def call(self, input: SearchInput, ctx: ToolContext) -> ToolResult:
        results = await my_db.search(input.query, limit=input.max_results)
        if not results:
            return ToolResult.error("Aucun résultat", name=self.name)
        return ToolResult.ok(
            name=self.name,
            content="\n".join(str(r) for r in results),
        )


agent = Agent(provider=provider, tools=[MySearchTool()])
```

### API BaseTool

| Attribut / Méthode | Description |
|---|---|
| `name: str` | Nom exposé au LLM |
| `description: str` | Description (utilisée par le LLM pour décider) |
| `input_schema: type[BaseModel]` | Schéma Pydantic des arguments |
| `check_fn: Callable[[], bool] \| None` | Gate d'availability dynamique |
| `async call(input, ctx) → ToolResult` | Logique principale |
| `is_available() → bool` | Retourne False si check_fn échoue |
| `is_deferrable() → bool` | True = caché derrière le tool search bridge |
| `is_concurrency_safe() → bool` | False = exécuté séquentiellement |

---

## check_fn — disponibilité conditionnelle

Cache un outil au LLM quand une dépendance est absente :

```python
import shutil

class BrowserTool(BaseTool):
    name = "browser"
    description = "Ouvre une page web"
    input_schema = BrowserInput
    check_fn = staticmethod(lambda: shutil.which("chromium") is not None)

    async def call(self, input, ctx):
        ...
```

Ou directement sur une instance :

```python
tool = MyApiTool()
tool.check_fn = lambda: os.getenv("MY_API_KEY") is not None

agent = Agent(provider=provider, tools=[tool])
# Si MY_API_KEY absente → outil invisible pour le LLM
```

---

## Tool Search Bridge

Pour les registres avec beaucoup d'outils MCP (au-delà du seuil de tokens), le bridge cache les outils déférables et expose 3 meta-outils à la place :

```python
agent = Agent(
    provider=provider,
    mcp_servers=[...],                   # beaucoup d'outils MCP
    tool_search_threshold=8_000,         # seuil en tokens de schémas
)
```

Les 3 meta-outils injectés automatiquement :

| Outil LLM | Description |
|---|---|
| `tool_search` | Cherche des outils par query textuelle |
| `tool_describe` | Obtient le schéma complet d'un outil |
| `tool_call` | Appelle un outil déféré par nom |

Les outils MCP implémentent `is_deferrable() → True` automatiquement. Les outils builtin sont toujours visibles.

---

## ToolContext — contexte d'exécution

Disponible dans `call(input, ctx)` :

```python
@dataclass
class ToolContext:
    session_id: str        # ID de la session courante
    agent_id: str          # ID de l'agent
    working_dir: str       # répertoire de travail
    permission_mode: str   # "auto" | "onRequest" | "bypass"
    sandbox: Any           # sandbox actif (si configuré)
    metadata: dict         # métadonnées custom (mailbox, task_board, …)
    sub_agent_depth: int   # profondeur d'imbrication
    max_sub_agent_depth: int
    parent_session_id: str # session parente (branching)
```

---

## ToolResult

```python
# Succès
return ToolResult.ok(name="my_tool", content="Résultat ici")

# Erreur
return ToolResult.error("Message d'erreur", name="my_tool")
```
