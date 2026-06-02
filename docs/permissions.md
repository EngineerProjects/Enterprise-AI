# Permissions — Modes et règles de sécurité

---

## Modes de permission

| Mode | Comportement |
|---|---|
| `"onRequest"` (défaut) | Demande confirmation avant chaque outil (si `ask_callback` configuré) |
| `"auto"` | Autorise tout (sauf règles de sécurité hardcodées) |
| `"bypass"` | Aucune vérification sauf les patterns dangereux absolus |

```python
agent = Agent(
    provider=provider,
    permission_mode="auto",   # ou PermissionMode.auto
)
```

---

## Blocage d'outils spécifiques

```python
agent = Agent(
    provider=provider,
    permission_mode="auto",
    deny_tools={"bash", "file_editor"},   # ces outils sont toujours bloqués
)
```

---

## Callback de confirmation (mode onRequest)

En mode `onRequest`, un callback peut approuver ou refuser chaque outil :

```python
from enterprise_ai.permissions.engine import PermissionEngine, PermissionMode
from enterprise_ai.schema import ToolCall

async def ask_user(tool_call: ToolCall) -> bool:
    print(f"L'agent veut utiliser '{tool_call.name}' avec : {tool_call.input}")
    answer = input("Autoriser ? (o/n) : ").strip().lower()
    return answer == "o"

permissions = PermissionEngine(
    mode=PermissionMode.on_request,
    ask_callback=ask_user,
)
```

---

## Outils toujours autorisés

Indépendamment du mode, certains outils ne nécessitent jamais de confirmation :

```python
ALWAYS_ALLOW_TOOLS = {"terminate", "code_search"}
```

---

## Règles de sécurité absolues (bypass impossible)

Ces patterns sont bloqués **même en mode bypass** :

| Pattern bloqué | Raison |
|---|---|
| `rm -rf /` | Suppression système |
| `rm -rf ~` | Suppression home |
| `:(){ :|:& };:` | Fork bomb |
| `mkfs` | Formatage disque |
| `/dev/sda` | Écriture disque brut |

Ces checks s'appliquent sur `str(tool_call.input).lower()`.

---

## Priorité des règles

```
1. deny_tools                → bloqué immédiatement (prioritaire)
2. safety_check (patterns)   → bloqué même en bypass
3. mode bypass               → tout le reste autorisé
4. ALWAYS_ALLOW_TOOLS        → toujours autorisé
5. mode auto                 → autorisé
6. mode onRequest            → ask_callback (ou autorisé par défaut si pas de callback)
```

---

## Sandbox — isolation d'exécution

Pour exécuter le code agent dans un environnement isolé :

```python
from enterprise_ai.sandbox.local import LocalSandbox
from enterprise_ai.sandbox.docker import DockerSandbox

# Sandbox local (répertoire isolé)
sandbox = LocalSandbox(working_dir="/tmp/agent-workspace")

# Sandbox Docker (isolation complète)
sandbox = DockerSandbox(
    image="python:3.12-slim",
    working_dir="/workspace",
)

# Utilisation directe
async with sandbox:
    result = await sandbox.exec("ls -la")
    print(result.output)
    await sandbox.write_file("script.py", "print('hello')")
    content = await sandbox.read_file("script.py")
```

Voir [Sandbox](sandbox.md) pour la documentation complète.
