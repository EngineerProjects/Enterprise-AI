from __future__ import annotations

from pathlib import Path

from enterprise_ai.skills.loader import load_skill_file
from enterprise_ai.skills.skill import Skill

# Built-in skills shipped with the package
_BUILTIN_DIR = Path(__file__).parent / "builtin"

# User skill directories (searched in order — first match wins)
_USER_DIRS = [
    Path.cwd() / ".enterprise-ai" / "skills",   # project-level (highest priority)
    Path.home() / ".enterprise-ai" / "skills",  # user-level
]


class SkillRegistry:
    """
    Loads and resolves skills by name.

    Search order (first match wins):
    1. {project}/.enterprise-ai/skills/
    2. ~/.enterprise-ai/skills/
    3. Built-in skills (shipped with the package)

    Skills are loaded lazily on first access and cached.
    """

    def __init__(self, extra_dirs: list[Path] | None = None) -> None:
        self._cache: dict[str, Skill] = {}
        self._loaded = False
        self._extra_dirs = extra_dirs or []

    def _search_dirs(self) -> list[Path]:
        dirs = self._extra_dirs + _USER_DIRS + [_BUILTIN_DIR]
        return [d for d in dirs if d.exists()]

    def _load_all(self) -> None:
        if self._loaded:
            return
        for directory in reversed(self._search_dirs()):
            for path in sorted(directory.rglob("*.md")):
                try:
                    skill = load_skill_file(path)
                    self._cache[skill.name] = skill
                except Exception:
                    pass
        self._loaded = True

    def get(self, name: str) -> Skill | None:
        self._load_all()
        return self._cache.get(name)

    def resolve(self, names: list[str]) -> list[Skill]:
        """Resolve a list of skill names, silently skipping unknown ones."""
        self._load_all()
        return [self._cache[n] for n in names if n in self._cache]

    def all(self) -> list[Skill]:
        self._load_all()
        return list(self._cache.values())

    def register(self, skill: Skill) -> None:
        """Register a skill programmatically (takes priority over file-based)."""
        self._cache[skill.name] = skill

    def reload(self) -> None:
        self._cache.clear()
        self._loaded = False


# Module-level default registry
_default_registry = SkillRegistry()


def get_registry() -> SkillRegistry:
    return _default_registry


def resolve_skills(names: list[str]) -> list[Skill]:
    return _default_registry.resolve(names)
