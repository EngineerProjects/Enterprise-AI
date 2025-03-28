# Implementation Order for LLM Feature Module

Now that you've implemented `base.py`, here's the logical order to follow for the rest of the LLM feature module. This sequence minimizes circular dependencies by building from fundamental components to more complex ones:

## 1. Constants and Types (Foundation Layer)

- **`constants.py`** - Define LLM-specific constants (model contexts, rate limits, etc.)
- **`types.py`** - Add any LLM-specific types beyond what's in core types.py (if needed)

## 2. Utility Layer

- **`retry.py`** - Implement retry mechanisms for API calls (you've already created this in Ollama)
- **`image.py`** - Image processing utilities for vision models
- **`utils.py`** - General utility functions for LLM operations

## 3. Provider Foundation

- **`providers/__init__.py`** - Basic exports and provider registration structure
- **`providers/registry.py`** - Provider registration and lookup system

## 4. Individual Providers

- **`providers/openai_provider.py`** - OpenAI implementation
- **`providers/anthropic_provider.py`** - Anthropic implementation
- You already have Ollama implemented

## 5. Provider Factory

- **`providers/factory.py`** - Provider instantiation and configuration functions

## 6. Caching System

- **`cache.py`** - Base caching mechanism for LLM responses

## 7. Service Layer (Bottom-Up)

- **`service/core.py`** - Core service implementation
- **`service/cache.py`** - Service-specific caching implementation
- **`service/metrics.py`** - Performance metrics collection
- **`service/pools.py`** - Provider pooling mechanisms
- **`service/orchestration.py`** - Request orchestration

## 8. Service Integration

- **`service/__init__.py`** - Service layer exports
- **`service/defaults.py`** - Default service instances

## 9. Package Exports

- **`__init__.py`** - Main LLM package exports

This approach follows a clear dependency flow while giving you checkpoints along the way. Each layer builds on the previous ones, and you can test components incrementally before moving to more complex integrations.

I recommend implementing both `constants.py` and `types.py` next, as they establish the foundation for the rest of the module. Would you like me to provide the implementation for those files to get you started?

______________________________________________________________________

# Prompt for AI-Assisted Enterprise AI Project Restructuring

I need help restructuring my Enterprise AI project to eliminate circular imports and establish a clean, maintainable architecture. I plan to create a new repository implementing best practices from scratch rather than refactoring the existing code.

## Project Context

My project is an Enterprise AI framework for creating autonomous AI teams with specialized roles that can collaborate on complex tasks. The codebase currently suffers from circular import issues, particularly between the configuration system and LLM service components.

## Core Principles I Want to Implement

1. **Strict Hierarchy**: Core foundation modules must never import from feature-specific modules
1. **One-Way Dependencies**: Dependencies should flow only from feature modules to core modules
1. **Separation of Concerns**: Clear separation between interfaces/models and implementations
1. **Modular Design**: Well-defined components with minimal coupling

## Proposed Core Structure

I want to structure my core foundation like this:

```
enterprise_ai/
├── __init__.py                # Package exports, version
├── constants.py               # System-wide constants
├── types.py                   # Type definitions, interfaces, protocols
├── exceptions.py              # All exception classes
├── py.typed                   # Type checking marker
├── schema.py                  # Data models (no feature imports)
├── version.py                 # Version info only
├── config/                    # Configuration system
│   ├── __init__.py            # Public exports
│   ├── constants.py           # Config-specific constants
│   ├── models.py              # Configuration models
│   ├── loaders.py             # YAML/TOML loading utilities
│   ├── providers.py           # Provider-specific config
│   ├── utils.py               # Helper functions
│   └── singleton.py           # Singleton pattern implementation
└── logger/                    # Logging system
    ├── __init__.py            # Public exports
    ├── config.py              # Logger configuration
    ├── formatters.py          # Log formatters
    ├── handlers.py            # Custom log handlers
    └── utils.py               # Helper functions
```

## Feature Module Structure

```
enterprise_ai/
└── llm/                       # LLM functionality
    ├── __init__.py
    ├── constants.py           # LLM-specific constants
    ├── types.py               # LLM-specific types
    ├── utils.py               # General LLM utilities
    ├── image.py               # Image processing (no schema imports)
    ├── base.py                # Base provider interface
    ├── retry.py               # Retry mechanisms
    ├── providers/             # Provider implementations
    │   ├── __init__.py
    │   ├── openai_provider.py
    │   ├── anthropic_provider.py
    │   └── ollama_provider.py
    └── service/               # Service layer
        ├── __init__.py        # Careful import order
        ├── cache.py           # Caching implementation
        ├── metrics.py         # Performance metrics
        ├── pools.py           # Provider pooling
        ├── registry.py        # Provider registration
        ├── orchestration.py   # Request orchestration
        ├── core.py            # Core service (no config imports)
        └── defaults.py        # Default service (delayed imports)
```

And other feature modules like `agent/`, `team/`, `tool/`, etc will come later. For the moment we'll focus on llm feature, that will be the heart of my project.

## Rules for Dependencies

1. Core files (`constants.py`, `exceptions.py`, `types.py`, `schema.py`, `version.py`) must not import any feature-specific modules
1. Core packages (`config/`, `logger/`) may import from core files but not from feature modules
1. Feature modules can import from any core file/package
1. Feature modules may import from other feature modules but should avoid circular dependencies
1. Use interfaces defined in `types.py` rather than concrete implementations
1. Employ lazy loading or dependency injection where appropriate

```
constants.py
    ↑
exceptions.py
    ↑
types.py ← schema.py ← config/models.py
    ↑           ↑          ↑
config/loaders.py    config/__init__.py
        ↑                  ↑
    logger/          feature modules
```

## What I Need Help With

1. You will find that I provide the old version of the project that I want to ameliorate, and the new version, you will se where I stop the devolopment.
1. Analyse thorougly all the file I provide to well understand everything
1. tell me the is the best file to chose to develop next, and give me the code of that file based on all what I have done yet and avoid circular import, so you have to take that in account.

I want to build this project with professional standards from the ground up, ensuring it's maintainable, modular, and free from the dependency issues that plagued the previous implementation.
