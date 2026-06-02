# enterprise-ai — Documentation

**enterprise-ai** est un SDK Python async-first pour construire des workflows multi-agents autonomes. Un `Agent` prend un prompt, exécute une boucle multi-tours (LLM → outils → LLM) et retourne un résultat ou stream des événements. Une `Team` coordonne plusieurs agents avec des rôles distincts.

```
pip install enterprise-ai
```

---

## Navigation

| Document | Contenu |
|---|---|
| [Quickstart](quickstart.md) | Installation, premier agent, exemples de base |
| [Agent](agent.md) | Référence complète de la classe `Agent` |
| [Providers](providers.md) | LLMs supportés, credential pool, retry, fallback |
| [Tools](tools.md) | Outils intégrés, outils custom, toolsets, check_fn |
| [Skills](skills.md) | Fichiers skill, preprocessing, SkillCurator |
| [Memory](memory.md) | Mémoire session, long-term, compaction, ContextEngine |
| [Team & MoA](team.md) | Team multi-agent, MixtureOfAgents |
| [Hooks](hooks.md) | Système d'événements, stop hooks |
| [MCP](mcp.md) | Intégration Model Context Protocol |
| [Streaming](streaming.md) | Événements stream, TagScrubber |
| [Permissions](permissions.md) | Modes de permission, règles de sécurité |
| [Sandbox](sandbox.md) | Exécution isolée (local, Docker) |

**Docs projet** (vision, roadmap, architecture interne) → [`docs/project/`](project/)

---

## Architecture en une phrase par couche

```
Agent          → interface publique, coordonne tout
QueryLoop      → boucle multi-tours : appel LLM → outils → LLM
Orchestrator   → exécution parallèle des tool calls, pipeline de permission
Provider       → abstraction LLM (Anthropic, OpenAI, Ollama, …)
ToolRegistry   → catalogue des outils disponibles
SessionMemory  → historique de conversation + compaction
```

---

## Exemple minimal

```python
import asyncio
from enterprise_ai import Agent
from enterprise_ai.providers import AnthropicProvider
from enterprise_ai.tools.builtin import BashTool, FileEditorTool

agent = Agent(
    provider=AnthropicProvider(model="claude-opus-4-8"),
    tools=[BashTool(), FileEditorTool()],
    system_prompt="Tu es un ingénieur Python senior.",
)

result = asyncio.run(agent.run("Corrige le test qui échoue dans tests/auth_test.py"))
print(result.output)
```
