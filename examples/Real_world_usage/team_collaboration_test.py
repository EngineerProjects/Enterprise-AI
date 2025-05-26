#!/usr/bin/env python
"""
Enterprise AI - Team Collaboration Test

This script creates a team of specialized AI agents that work together
to accomplish complex tasks through collaboration:
- Multiple agents with different specializations
- Proper team hierarchy and communication
- Tool sharing and coordination
- Real-world team scenarios
- Clean logging and visual progress indicators

This test validates the team collaboration capabilities of the Enterprise AI framework.
"""

from pathlib import Path
from enum import Enum

# Rich imports for beautiful terminal output
from rich.console import Console
from rich.panel import Panel
import logging

from enterprise_ai.logger import get_logger, setup_logger


# Setup workspace and logging
WORKSPACE_DIR = Path(__file__).parent / "workspace"
TEAM_LOG_FILE = WORKSPACE_DIR / "team_collaboration.log"
WORKSPACE_DIR.mkdir(exist_ok=True)

# Setup logging to file
setup_logger(
    name="single_agent_test",
    level="INFO",
)

logger = get_logger("team_collaboration_test")
console = Console()


def print_header():
    """Print beautiful header for the team test."""
    header_text = """
    ████████╗███████╗ █████╗ ███╗   ███╗     ██████╗ ██████╗ ██╗     ██╗      █████╗ ██████╗ 
    ╚══██╔══╝██╔════╝██╔══██╗████╗ ████║    ██╔════╝██╔═══██╗██║     ██║     ██╔══██╗██╔══██╗
       ██║   █████╗  ███████║██╔████╔██║    ██║     ██║   ██║██║     ██║     ███████║██████╔╝
       ██║   ██╔══╝  ██╔══██║██║╚██╔╝██║    ██║     ██║   ██║██║     ██║     ██╔══██║██╔══██╗
       ██║   ███████╗██║  ██║██║ ╚═╝ ██║    ╚██████╗╚██████╔╝███████╗███████╗██║  ██║██████╔╝
       ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝     ╚═════╝ ╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═╝╚═════╝ 
                                
                          🤝 TEAM COLLABORATION TEST 🤝
    """
    console.print(Panel(header_text, style="bold magenta", padding=(1, 2)))

if __name__ == "__main__":
    print_header()