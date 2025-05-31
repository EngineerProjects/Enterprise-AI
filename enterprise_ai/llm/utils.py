"""
Production utilities for Enterprise AI LLM module.
"""

from typing import Any, List
from contextlib import contextmanager, asynccontextmanager

from enterprise_ai.llm.base import cleanup_all_providers, acleanup_all_providers
from enterprise_ai.llm.factory import create_provider
from enterprise_ai.logger import get_logger
from enterprise_ai.types import MessageProtocol

logger = get_logger("llm.utils")


@contextmanager
def managed_provider(provider_name: str, **kwargs: Any):
    """Context manager for automatic provider cleanup."""
    provider = None
    try:
        provider = create_provider(provider_name, **kwargs)
        yield provider
    finally:
        if provider:
            try:
                provider.close()
            except Exception as e:
                logger.warning(f"Error closing provider: {e}")


@asynccontextmanager
async def amanaged_provider(provider_name: str, **kwargs: Any):
    """Async context manager for automatic provider cleanup."""
    provider = None
    try:
        provider = create_provider(provider_name, **kwargs)
        yield provider
    finally:
        if provider:
            try:
                await provider.aclose()
            except Exception as e:
                logger.warning(f"Error closing provider: {e}")



def format_conversation(messages: List[MessageProtocol]) -> str:
    """Format a list of messages as a readable conversation."""
    formatted = []
    for i, msg in enumerate(messages):
        if hasattr(msg, 'role') and hasattr(msg, 'content'):
            role = msg.role.capitalize()
            content = msg.content or ""
            formatted.append(f"{role}: {content}")
        else:
            formatted.append(f"Message {i}: {str(msg)}")
    return "\n".join(formatted)


def emergency_cleanup() -> None:
    """Emergency cleanup function to close all active providers."""
    try:
        cleanup_all_providers()
        logger.info("Emergency cleanup completed")
    except Exception as e:
        logger.error(f"Error during emergency cleanup: {e}")


async def aemergency_cleanup() -> None:
    """Async emergency cleanup function to close all active providers."""
    try:
        await acleanup_all_providers()
        logger.info("Async emergency cleanup completed")
    except Exception as e:
        logger.error(f"Error during async emergency cleanup: {e}")
