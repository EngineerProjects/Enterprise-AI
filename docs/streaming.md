# Streaming — Événements et scrubbers

---

## Événements de stream

`agent.stream()` émet un `AsyncIterator[StreamEvent]`. Chaque événement a un `type` et un `data`.

```python
async for event in agent.stream("Analyse ce fichier"):
    match event.type.value:
        case "text_delta":
            print(event.data["delta"], end="", flush=True)
        case "tool_start":
            print(f"\n→ outil : {event.data['name']}")
        case "tool_result":
            print(f"← résultat : {event.data['content'][:100]}")
        case "thinking":
            pass   # blocs de réflexion (extended thinking)
        case "session_end":
            print(f"\n✓ Terminé : {event.data['output'][:80]}")
```

### Tous les types d'événements

| `event.type.value` | `event.data` | Description |
|---|---|---|
| `text_delta` | `{"delta": "..."}` | Chunk de texte en cours de génération |
| `tool_start` | `{"id": "...", "name": "...", "input": {...}}` | Début d'un outil |
| `tool_result` | `{"id": "...", "name": "...", "content": "..."}` | Résultat d'un outil |
| `thinking` | `{"delta": "..."}` | Chunk de thinking (extended thinking) |
| `session_end` | `{"output": "...", "thinking_blocks": [...]}` | Fin de session |
| `error` | `{"error": "...", "type": "..."}` | Erreur |

---

## StreamScrubber — filtres de stream

Les scrubbers transforment le texte des `text_delta` en temps réel. Ils sont **stateful** et gèrent les tags qui se coupent sur les frontières de chunks.

### TagScrubber — supprimer des balises XML

Filtre tout le contenu entre une balise ouvrante et fermante :

```python
from enterprise_ai.stream import TagScrubber

# Supprimer les blocs <thinking>...</thinking> du stream
scrubber = TagScrubber(open_tag="<thinking>", close_tag="</thinking>")

agent = Agent(
    provider=provider,
    stream_scrubbers=[scrubber],
)

async for event in agent.stream("Analyse ce problème"):
    if event.type.value == "text_delta":
        print(event.data["delta"], end="")
# Les blocs <thinking> sont invisibles dans le stream
```

### Plusieurs scrubbers

```python
from enterprise_ai.stream import TagScrubber

agent = Agent(
    provider=provider,
    stream_scrubbers=[
        TagScrubber("<thinking>", "</thinking>"),     # filtrer le thinking
        TagScrubber("<internal>", "</internal>"),     # filtrer les notes internes
        TagScrubber("<draft>", "</draft>"),           # filtrer les brouillons
    ],
)
```

### Scrubber custom

Implémente `StreamScrubber` pour une logique de filtrage arbitraire :

```python
from enterprise_ai.stream import StreamScrubber

class RedactEmailScrubber(StreamScrubber):
    """Remplace les adresses email par [EMAIL] dans le stream."""

    def __init__(self):
        self._buf = ""
        self._in_block = False

    def process(self, chunk: str) -> str:
        import re
        return re.sub(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}", "[EMAIL]", chunk)

    def reset(self) -> None:
        self._buf = ""
        self._in_block = False

    @property
    def in_block(self) -> bool:
        return self._in_block

agent = Agent(
    provider=provider,
    stream_scrubbers=[RedactEmailScrubber()],
)
```

### ABC StreamScrubber

```python
from abc import ABC, abstractmethod

class StreamScrubber(ABC):
    @abstractmethod
    def process(self, chunk: str) -> str:
        """Transforme un chunk entrant. Retourne le chunk filtré (peut être vide)."""
        ...

    @abstractmethod
    def reset(self) -> None:
        """Réinitialise l'état interne entre deux sessions de streaming."""
        ...

    @property
    @abstractmethod
    def in_block(self) -> bool:
        """True si le scrubber est actuellement dans un bloc qu'il filtre."""
        ...
```

---

## Gestion des tags coupés

`TagScrubber` gère correctement les cas où un tag se coupe sur la frontière entre deux chunks :

```
Chunk 1 : "Voici ma réponse. <thin"
Chunk 2 : "king>Réflexion interne</thinking> Suite."
```

Le scrubber bufferise le préfixe partiel (`<thin`) entre les chunks et reconstruit correctement le filtrage. L'output produit est `"Voici ma réponse.  Suite."`.

---

## Assembler le stream en résultat complet

Pour collecter tout le texte final depuis un stream :

```python
async def collect_stream(agent, prompt) -> str:
    parts = []
    async for event in agent.stream(prompt):
        if event.type.value == "text_delta":
            parts.append(event.data["delta"])
        elif event.type.value == "session_end":
            return event.data["output"]
    return "".join(parts)
```
