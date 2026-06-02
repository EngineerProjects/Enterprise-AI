# Quickstart

## Installation

```bash
pip install enterprise-ai
```

Avec des extras optionnels :

```bash
pip install "enterprise-ai[docker]"      # sandbox Docker
pip install "enterprise-ai[mcp]"         # Model Context Protocol
pip install "enterprise-ai[ddgs]"        # DuckDuckGo web search
pip install "enterprise-ai[bedrock]"     # AWS Bedrock
pip install "enterprise-ai[server]"      # FastAPI HTTP server
```

---

## Clé API

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

---

## Premier agent

```python
import asyncio
from enterprise_ai import Agent
from enterprise_ai.providers import AnthropicProvider
from enterprise_ai.tools.builtin import BashTool, FileEditorTool

agent = Agent(
    provider=AnthropicProvider(model="claude-opus-4-8"),
    tools=[BashTool(), FileEditorTool()],
    system_prompt="Tu es un ingénieur Python expérimenté.",
)

result = asyncio.run(agent.run("Liste les fichiers Python dans le répertoire courant"))
print(result.output)
```

---

## Streaming

```python
import asyncio
from enterprise_ai import Agent
from enterprise_ai.providers import AnthropicProvider

agent = Agent(provider=AnthropicProvider())

async def main():
    async for event in agent.stream("Explique les générateurs Python"):
        if event.type.value == "text_delta":
            print(event.data["delta"], end="", flush=True)

asyncio.run(main())
```

---

## Plusieurs providers

```python
from enterprise_ai.providers import create_provider

# Anthropic (natif)
p = create_provider("anthropic", model="claude-opus-4-8")

# OpenAI
p = create_provider("openai", model="gpt-4o")

# Local Ollama (aucune clé requise)
p = create_provider("ollama", model="llama3.1")

# OpenRouter (accès à des centaines de modèles)
p = create_provider("openrouter", model="meta-llama/llama-3-70b-instruct")

# Mistral / Gemini / DeepSeek / Groq / xAI
p = create_provider("mistral")
p = create_provider("gemini")
p = create_provider("deepseek")
p = create_provider("groq")
p = create_provider("xai")
```

---

## Toolset intégré (raccourci)

Au lieu de lister les outils un par un, utilise un toolset prédéfini :

```python
agent = Agent(
    provider=AnthropicProvider(),
    toolset="development",   # bash + file_editor + code_search + terminate
)
```

Toolsets disponibles : `minimal`, `development`, `research`, `full`, `team_worker`.

---

## Équipe multi-agents

```python
import asyncio
from enterprise_ai import Agent, Team
from enterprise_ai.providers import AnthropicProvider

team = Team(
    agents=[
        Agent(
            provider=AnthropicProvider(),
            toolset="team_worker",
            system_prompt="Tu es le chef de projet. Décompose la mission et poste des tâches.",
        ),
        Agent(
            provider=AnthropicProvider(),
            toolset="team_worker",
            system_prompt="Tu es développeur. Prends les tâches de développement et implémente-les.",
        ),
    ]
)

result = asyncio.run(team.run("Implémente une API REST pour la gestion d'utilisateurs"))
print(result.combined_output)
```

---

## Prochaines étapes

- [Agent](agent.md) — tous les paramètres, méthodes, session branching
- [Tools](tools.md) — créer des outils custom
- [Skills](skills.md) — injecter des procédures réutilisables
- [Memory](memory.md) — persistance entre sessions
- [Providers](providers.md) — retry, fallback, credential pool
