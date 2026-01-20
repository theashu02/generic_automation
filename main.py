#!/usr/bin/env python3
"""
Vision Agent - Automatic Job Application Filler
Main entry point with CLI interface.

Usage:
    python main.py --url "https://jobs.lever.co/company/apply"
    python main.py --url "URL" --som  # Enable Set-of-Mark for complex UIs
"""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from src.vision_agent import VisionAgent
from src.utils import load_user_data, ensure_directories

console = Console()


def print_banner():
    """Print the application banner."""
    banner = """
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║   🤖 Vision Agent - Automatic Job Application Filler              ║
║                                                                   ║
║   Powered by GPT-4o Vision + Playwright                           ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
    """
    console.print(banner, style="bold blue")


@click.command()
@click.option(
    '--url', '-u',
    required=True,
    help='Job application URL to fill'
)
@click.option(
    '--user-data', '-d',
    default=None,
    help='Path to user.json (default: user_data/user.json)'
)
@click.option(
    '--resume', '-r',
    default=None,
    help='Path to resume PDF (default: user_data/resume.pdf)'
)
@click.option(
    '--som', '-s',
    is_flag=True,
    default=False,
    help='Enable Set-of-Mark for precise element targeting'
)
@click.option(
    '--headless', '-h',
    is_flag=True,
    default=False,
    help='Run browser in headless mode'
)
@click.option(
    '--max-steps', '-m',
    default=30,
    type=int,
    help='Maximum automation steps (default: 30)'
)
@click.option(
    '--delay',
    default=1.0,
    type=float,
    help='Delay between actions in seconds (default: 1.0)'
)
@click.option(
    '--cover-letter', '-c',
    default=None,
    help='Path to cover letter text file (default: user_data/coverletter.txt)'
)
@click.option(
    '--yes', '-y',
    is_flag=True,
    default=False,
    help='Skip the start confirmation prompt (run fully unattended)'
)
def main(url: str, user_data: str, resume: str, som: bool, headless: bool, max_steps: int, delay: float, cover_letter: str, yes: bool):
    """
    Automatically fill job applications using AI vision.
    
    The agent will navigate to the provided URL, analyze the page using GPT-4o,
    and fill the application form using data from your user.json profile.
    """
    print_banner()
    
    # Ensure required directories exist
    Config.ensure_directories()
    
    # Validate configuration
    if not Config.validate():
        console.print("\n[bold red]Please set up your .env file with OPENAI_API_KEY[/bold red]")
        console.print("[dim]Copy .env.example to .env and add your API key[/dim]")
        sys.exit(1)
    
    # Resolve paths
    user_data_path = Path(user_data) if user_data else Config.get_default_user_data_path()
    resume_path = Path(resume) if resume else Config.get_default_resume_path()
    cover_letter_path = Path(cover_letter) if cover_letter else Config.USER_DATA_DIR / "coverletter.txt"
    
    # Validate user data exists
    if not user_data_path.exists():
        console.print(f"\n[bold red]User data not found: {user_data_path}[/bold red]")
        console.print("[dim]Edit user_data/user.json with your information[/dim]")
        sys.exit(1)
    
    # Validate resume exists (warning only, some applications don't require it)
    if not resume_path.exists():
        console.print(f"\n[yellow]⚠ Resume not found: {resume_path}[/yellow]")
        console.print("[dim]Some applications may require a resume upload[/dim]")
    
    # Load and validate user data
    loaded_data = load_user_data(user_data_path)
    if not loaded_data:
        sys.exit(1)
    
    # Print configuration summary
    console.print(Panel(
        f"[bold]URL:[/bold] {url}\n"
        f"[bold]User Data:[/bold] {user_data_path}\n"
        f"[bold]Resume:[/bold] {resume_path}\n"
        f"[bold]Cover Letter:[/bold] {cover_letter_path if cover_letter_path.exists() else 'Not found'}\n"
        f"[bold]Set-of-Mark:[/bold] {'Enabled' if som or Config.ENABLE_SOM else 'Disabled'}\n"
        f"[bold]Headless:[/bold] {'Yes' if headless or Config.HEADLESS else 'No'}\n"
        f"[bold]Max Steps:[/bold] {max_steps}\n"
        f"[bold]Action Delay:[/bold] {delay}s",
        title="Configuration",
        border_style="cyan"
    ))
    
    # Confirm before starting
    console.print("\n[bold yellow]Ready to start automation.[/bold yellow]")
    if not yes and not click.confirm("Proceed?", default=True):
        console.print("[dim]Cancelled by user[/dim]")
        sys.exit(0)
    
    # Initialize and run the agent
    try:
        agent = VisionAgent(
            user_data_path=user_data_path,
            resume_path=resume_path,
            api_key=Config.OPENAI_API_KEY,
            headless=headless or Config.HEADLESS,
            max_steps=max_steps,
            action_delay=delay,
            screenshot_width=Config.SCREENSHOT_WIDTH,
            enable_som=som or Config.ENABLE_SOM,
            cover_letter_path=cover_letter_path if cover_letter_path.exists() else None
        )
        
        success = agent.run(url)
        
        if success:
            console.print("\n[bold green]🎉 Job application completed successfully![/bold green]")
            sys.exit(0)
        else:
            console.print("\n[bold yellow]⚠ Automation ended without confirmation of submission[/bold yellow]")
            console.print("[dim]Check screenshots folder for the final state[/dim]")
            sys.exit(1)
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[bold red]Fatal error: {e}[/bold red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
