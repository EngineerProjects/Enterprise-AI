#!/usr/bin/env python
"""
Enterprise AI - Test Launcher

Simple launcher to choose and run the appropriate test.
This utility validates that all prerequisites are met and
launches the selected test with proper configuration.
"""

import sys
import subprocess
import os
from pathlib import Path
from typing import List, Dict, Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

def print_header():
    """Print launcher header."""
    header = """
    ███████╗███╗   ██╗████████╗███████╗██████╗ ██████╗ ██████╗ ██╗███████╗███████╗
    ██╔════╝████╗  ██║╚══██╔══╝██╔════╝██╔══██╗██╔══██╗██╔══██╗██║██╔════╝██╔════╝
    █████╗  ██╔██╗ ██║   ██║   █████╗  ██████╔╝██████╔╝██████╔╝██║███████╗█████╗  
    ██╔══╝  ██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗██╔═══╝ ██╔══██╗██║╚════██║██╔══╝  
    ███████╗██║ ╚████║   ██║   ███████╗██║  ██║██║     ██║  ██║██║███████║███████╗
    ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝╚═╝╚══════╝╚══════╝
                                
                               🚀 TEST LAUNCHER 🚀
    """
    console.print(Panel(header, style="bold yellow", padding=(1, 2)))


def create_required_directories():
    """Create required directories if they don't exist."""
    base_dir = Path(__file__).parent
    
    # Create workspace directory
    workspace_dir = base_dir / "workspace"
    workspace_dir.mkdir(exist_ok=True)
    
    # Create prompt directory
    prompt_dir = base_dir / "prompts"
    prompt_dir.mkdir(exist_ok=True)
    
    return {
        "workspace": workspace_dir,
        "prompts": prompt_dir
    }


def check_prompt_files() -> bool:
    """Check if required prompt files exist and create them if missing."""
    base_dir = Path(__file__).parent
    prompt_dir = base_dir / "prompts"
    
    required_prompts = [
        "single_agent.prompt",
        "research_manager.prompt", 
        "data_analyst.prompt", 
        "research_specialist.prompt",
        "tech_lead.prompt",
        "backend_developer.prompt",
        "frontend_developer.prompt"
    ]
    
    missing_prompts = []
    for prompt in required_prompts:
        if not (prompt_dir / prompt).exists():
            missing_prompts.append(prompt)
    
    if missing_prompts:
        console.print(f"[yellow]Missing prompt files: {', '.join(missing_prompts)}[/]")
        console.print("[yellow]These will be generated with default values when tests are run.[/]")
        return False
    
    return True


def check_ollama_status() -> Dict[str, bool]:
    """Check if Ollama is running and if required models are available."""
    result = {
        "server_running": False,
        "models_available": False
    }
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Checking Ollama server...", total=None)
        
        try:
            import httpx
            response = httpx.get("http://localhost:11434/api/tags", timeout=5.0)
            
            if response.status_code == 200:
                result["server_running"] = True
                progress.update(task, description="Ollama server is running ✅")
                
                # Check for required models
                data = response.json()
                models = [model["name"] for model in data.get("models", [])]
                
                if any("llama3" in model.lower() for model in models):
                    result["models_available"] = True
                    progress.update(task, description="Required models are available ✅")
                else:
                    progress.update(task, description="Required models not found ❌")
                    console.print("[yellow]No Llama 3 models found. Available models:[/]")
                    for model in models:
                        console.print(f"   - {model}")
                    
                    console.print("\n[yellow]You can install a model with:[/]")
                    console.print("   [green]ollama pull llama3.2[/]")
            else:
                progress.update(task, description="Ollama server error ❌")
                
        except Exception as e:
            progress.update(task, description="Ollama server not accessible ❌")
            console.print(f"[red]Cannot connect to Ollama server: {e}[/]")
            console.print("[dim]Make sure Ollama is running: ollama serve[/]")
    
    return result


def check_prerequisites() -> bool:
    """Check if all prerequisites are met."""
    console.print("🔍 [yellow]Checking prerequisites...[/]")
    
    # Create required directories
    dirs = create_required_directories()
    console.print(f"✅ [green]Workspace directory created at: {dirs['workspace']}[/]")
    console.print(f"✅ [green]Prompts directory created at: {dirs['prompts']}[/]")
    
    # Check prompt files
    prompt_status = check_prompt_files()
    
    # Check Ollama status
    ollama_status = check_ollama_status()
    
    # If Ollama is not running or models are not available, ask to continue
    if not ollama_status["server_running"]:
        console.print("\n[red]Ollama server is not running.[/]")
        console.print("[yellow]You need to start Ollama first: ollama serve[/]")
        
        if Confirm.ask("Do you want to try starting Ollama automatically?"):
            try:
                subprocess.Popen(["ollama", "serve"], 
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE)
                console.print("[green]Attempting to start Ollama. Please wait a moment...[/]")
                import time
                time.sleep(5)  # Give it time to start
                
                # Check again
                retry_status = check_ollama_status()
                if not retry_status["server_running"]:
                    console.print("[red]Failed to start Ollama automatically.[/]")
                    return False
                ollama_status = retry_status
            except Exception as e:
                console.print(f"[red]Failed to start Ollama: {e}[/]")
                return False
    
    if not ollama_status["models_available"]:
        if Confirm.ask("No suitable models found. Continue anyway?"):
            console.print("[yellow]Continuing without recommended models. Tests may fail.[/]")
        else:
            return False
    
    return True


def main():
    """Main launcher function."""
    print_header()
    
    # Check prerequisites
    if not check_prerequisites():
        console.print("\n[red]Prerequisites not met. Please fix the issues above.[/]")
        return 1
    
    # Show test options
    console.print("\n[bold]Available Tests:[/]")
    options_text = """
[bold cyan]1. Single Agent Test[/]
   • Interactive session with one intelligent agent
   • Full tool access and ReAct reasoning
   • Great for testing individual agent capabilities
   
[bold cyan]2. Team Collaboration Test[/]  
   • Multiple specialized agents working together
   • Hierarchical team structure
   • Real agent-to-agent collaboration
   
[bold cyan]3. Both Tests (Sequential)[/]
   • Run single agent test first, then team test
   • Comprehensive validation of the entire package
"""
    
    console.print(Panel(options_text, title="Test Options", style="blue"))
    
    # Get user choice
    choice = IntPrompt.ask(
        "\n[bold]Select test to run[/]",
        choices=["1", "2", "3"],
        default=1
    )
    
    # Run selected test(s)
    current_dir = Path(__file__).parent
    
    try:
        if choice == 1:
            console.print("\n🚀 [green]Launching Single Agent Test...[/]")
            result = subprocess.run([
                sys.executable, 
                str(current_dir / "single_agent_test.py")
            ], cwd=current_dir)
            return result.returncode
            
        elif choice == 2:
            console.print("\n🚀 [green]Launching Team Collaboration Test...[/]")
            result = subprocess.run([
                sys.executable,
                str(current_dir / "team_collaboration_test.py")
            ], cwd=current_dir)
            return result.returncode
            
        elif choice == 3:
            console.print("\n🚀 [green]Running Both Tests...[/]")
            
            # Run single agent test first
            console.print("\n[bold]Phase 1: Single Agent Test[/]")
            result1 = subprocess.run([
                sys.executable,
                str(current_dir / "single_agent_test.py")
            ], cwd=current_dir)
            
            if result1.returncode != 0:
                console.print("[red]Single agent test failed. Stopping.[/]")
                return result1.returncode
            
            # Ask if user wants to continue
            if not Confirm.ask("\nContinue with team collaboration test?"):
                return 0
            
            # Run team collaboration test
            console.print("\n[bold]Phase 2: Team Collaboration Test[/]")
            result2 = subprocess.run([
                sys.executable,
                str(current_dir / "team_collaboration_test.py")
            ], cwd=current_dir)
            
            return result2.returncode
    
    except KeyboardInterrupt:
        console.print("\n[yellow]Test launcher interrupted by user[/]")
        return 1
    except Exception as e:
        console.print(f"\n[red]Error running test: {e}[/]")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
