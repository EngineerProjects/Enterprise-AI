# Providers — LLMs supportés & Résilience

---

## Providers disponibles

### Anthropic (natif)

```python
from enterprise_ai.providers import AnthropicProvider

provider = AnthropicProvider(
    model="claude-opus-4-8",     # ou claude-sonnet-4-6, claude-haiku-4-5-20251001
    api_key="sk-ant-...",        # optionnel : lit ANTHROPIC_API_KEY par défaut
    api_keys=["key1", "key2"],   # pool de clés (rotation sur 429)
)
```

### OpenAI

```python
from enterprise_ai.providers import OpenAIProvider

provider = OpenAIProvider(
    model="gpt-4o",
    api_key="sk-...",
)
```

### Factory universelle

```python
from enterprise_ai.providers import create_provider

# Tous les providers supportés
create_provider("anthropic",  model="claude-opus-4-8")
create_provider("openai",     model="gpt-4o")
create_provider("openrouter", model="meta-llama/llama-3-70b-instruct")
create_provider("ollama",     model="llama3.1")          # local, aucune clé
create_provider("mistral",    model="mistral-large-latest")
create_provider("gemini",     model="gemini-2.0-flash")
create_provider("deepseek",   model="deepseek-chat")
create_provider("groq",       model="llama-3.3-70b-versatile")
create_provider("xai",        model="grok-3")
create_provider("bedrock",    model="anthropic.claude-3-5-sonnet-20241022-v2:0")
```

Variables d'environnement lues automatiquement :

| Provider | Variable |
|---|---|
| anthropic | `ANTHROPIC_API_KEY` |
| openai | `OPENAI_API_KEY` |
| openrouter | `OPENROUTER_API_KEY` |
| mistral | `MISTRAL_API_KEY` |
| gemini | `GOOGLE_API_KEY` |
| deepseek | `DEEPSEEK_API_KEY` |
| groq | `GROQ_API_KEY` |
| xai | `XAI_API_KEY` |
| ollama | aucune clé requise |

---

## Credential Pool — rotation de clés

Quand plusieurs clés sont disponibles, le pool tourne automatiquement sur code 429 avant d'attendre le backoff :

```python
provider = AnthropicProvider(
    api_keys=["sk-ant-prod-1", "sk-ant-prod-2", "sk-ant-prod-3"],
)
# Sur 429 : clé 1 → clé 2 → clé 3 → backoff → réessai depuis clé 1
```

Comportement :
- La rotation se fait **dans** le provider, sans délai entre les clés
- La boucle de retry ne voit qu'un seul 429 par rotation complète
- `pool.size` : nombre de clés — `pool.rotate()` : retourne `True` si toutes épuisées

---

## Retry & Backoff

```python
from enterprise_ai.providers.retry import RetryConfig

agent = Agent(
    provider=provider,
    retry_config=RetryConfig(
        max_attempts=4,          # 4 tentatives au total
        base_delay_ms=1_000,     # 1s initial
        max_delay_ms=60_000,     # cap à 60s
        multiplier=2.0,          # exponentiel ×2
        jitter_factor=0.25,      # ±25% aléatoire
        retryable_status_codes=frozenset({429, 500, 502, 503, 504}),
    ),
)
```

---

## Fallback Provider

Quand le provider primaire échoue avec une erreur non-transitoire (401, 403, 400), le fallback est tenté automatiquement :

```python
agent = Agent(
    provider=AnthropicProvider(model="claude-opus-4-8"),
    fallback_provider=create_provider("openai", model="gpt-4o"),
    retry_config=RetryConfig(max_attempts=3),
)
```

Logique de décision :

| Code HTTP | Classe | Comportement |
|---|---|---|
| 429, 5xx | `TRANSIENT` | Retry avec backoff, puis fallback si épuisé |
| 400, 401, 403 | `FALLBACK` | Fallback immédiat (sans retry) |
| 404, 410 | `FATAL` | Erreur immédiate, pas de fallback |
| Pas de status code | — | Non retryable |

---

## Buffering des événements de retry

Par défaut, les événements de retry (`type: "retry"`) sont **bufferisés** et ne sont émis que si la session échoue. En cas de succès final, le retry est silencieux. Ce comportement est automatique et ne se configure pas.

---

## Prompt Caching (Anthropic)

Active le cache Anthropic pour économiser sur les appels répétitifs avec le même system prompt :

```python
agent = Agent(
    provider=AnthropicProvider(),
    cache_system_prompt=True,
)

result = await agent.run("Question 1")
# result.cache_stats.cache_write_tokens > 0  (premier appel : écriture)

result2 = await agent.run("Question 2")
# result2.cache_stats.cache_read_tokens > 0  (appels suivants : lecture)
# result2.cache_stats.estimated_savings_pct  (ex : 72.5%)
```

Le cache Anthropic facture les lectures à ~10% du prix normal, soit ~90% d'économie par rapport à un input normal.

---

## Extended Thinking (Anthropic)

```python
agent = Agent(
    provider=AnthropicProvider(model="claude-opus-4-8"),
    extended_thinking=True,
    thinking_budget_tokens=16_000,
)
result = await agent.run("Résous ce problème d'optimisation complexe")
```

---

## Provider custom

Implémente l'ABC `Provider` pour brancher n'importe quel backend :

```python
from enterprise_ai.providers.base import Provider, LLMResponse
from enterprise_ai.schema import Message, StreamEvent

class MyProvider(Provider):
    @property
    def model(self) -> str:
        return "my-model-v1"

    async def complete(self, messages, tools=None, max_tokens=8096, **kwargs) -> LLMResponse:
        # Appelle ton API
        response = await my_api.call(messages)
        return LLMResponse(
            content=response.text,
            tool_calls=[],
            input_tokens=response.usage.input,
            output_tokens=response.usage.output,
        )

    async def stream(self, messages, tools=None, max_tokens=8096, **kwargs):
        async for chunk in my_api.stream(messages):
            yield StreamEvent.text(chunk.delta)
```
