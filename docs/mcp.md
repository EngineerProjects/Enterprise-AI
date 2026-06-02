# MCP — Model Context Protocol

Le SDK supporte nativement les serveurs MCP, permettant de brancher n'importe quel outil MCP existant (GitHub, Slack, Postgres, Brave Search, etc.).

**Prérequis** : `pip install "enterprise-ai[mcp]"`

---

## Types de serveurs

### Serveur stdio (local — le plus courant)

Le serveur tourne comme un sous-processus qui communique via stdin/stdout.

```python
from enterprise_ai.mcp.config import StdioServerConfig

# GitHub MCP via npx
github_mcp = StdioServerConfig(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-github"],
    env={"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_..."},
    name="github",
)

# Serveur Python local
my_server = StdioServerConfig(
    command="python",
    args=["my_mcp_server.py"],
    name="my-server",
)
```

### Serveur SSE (HTTP distant)

```python
from enterprise_ai.mcp.config import SSEServerConfig

remote_mcp = SSEServerConfig(
    url="http://localhost:3000/sse",
    headers={"Authorization": "Bearer my-token"},
    name="remote-server",
)
```

---

## Utilisation avec Agent

### Context manager (recommandé)

```python
from enterprise_ai import Agent
from enterprise_ai.providers import AnthropicProvider
from enterprise_ai.mcp.config import StdioServerConfig

agent = Agent(
    provider=AnthropicProvider(),
    mcp_servers=[
        StdioServerConfig(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env={"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_..."},
        ),
    ],
)

async with agent.mcp():
    result = await agent.run("Liste mes pull requests ouvertes sur anthropics/claude-code")
    print(result.output)
# Les connexions MCP sont fermées à la sortie du contexte
```

### Manuel

```python
await agent.connect_mcp()
try:
    result = await agent.run("...")
finally:
    await agent.disconnect_mcp()
```

---

## Plusieurs serveurs MCP

```python
agent = Agent(
    provider=AnthropicProvider(),
    mcp_servers=[
        StdioServerConfig(
            command="npx", args=["-y", "@modelcontextprotocol/server-github"],
            env={"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_..."},
            name="github",
        ),
        StdioServerConfig(
            command="npx", args=["-y", "@modelcontextprotocol/server-slack"],
            env={"SLACK_BOT_TOKEN": "xoxb-..."},
            name="slack",
        ),
        StdioServerConfig(
            command="npx", args=["-y", "@modelcontextprotocol/server-postgres"],
            env={"POSTGRES_CONNECTION_STRING": "postgresql://..."},
            name="postgres",
        ),
    ],
)

async with agent.mcp():
    result = await agent.run(
        "Récupère les PRs GitHub ouvertes, "
        "poste un résumé sur Slack #engineering, "
        "et logge les stats en base."
    )
```

---

## Tool Search Bridge pour grands registres MCP

Quand un serveur MCP expose des centaines d'outils, les schémas seuls peuvent dépasser le contexte LLM. Le **tool search bridge** cache les outils MCP et les rend accessibles via 3 meta-outils :

```python
agent = Agent(
    provider=AnthropicProvider(),
    mcp_servers=[large_mcp_server],
    tool_search_threshold=8_000,    # en tokens estimés de schémas
)
```

Quand le seuil est dépassé, le LLM voit :

| Outil | Description |
|---|---|
| `tool_search` | `tool_search(query="recherche de fichiers")` → liste les outils correspondants |
| `tool_describe` | `tool_describe(name="read_file")` → schéma complet de l'outil |
| `tool_call` | `tool_call(name="read_file", args={...})` → exécute l'outil |

Les outils builtin (`bash`, `file_editor`, etc.) restent toujours visibles.

---

## Outils MCP déférables

Tous les outils MCP sont automatiquement `is_deferrable() → True`. Les outils builtin ne sont jamais déférables.

Pour marquer un outil custom comme déférable :

```python
class MyLargeApiTool(BaseTool):
    name = "my_large_api"
    description = "API avec 500 endpoints"
    input_schema = MyInput

    def is_deferrable(self) -> bool:
        return True   # sera caché quand le bridge est actif

    async def call(self, input, ctx):
        ...
```

---

## Inspecter les outils chargés

```python
async with agent.mcp():
    # Lister tous les outils disponibles (builtin + MCP)
    tools = agent._registry.all()
    for tool in tools:
        print(f"{tool.name}: {tool.description}")

    result = await agent.run("Qu'est-ce que tu peux faire ?")
```
