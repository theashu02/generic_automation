"""
Utility functions for Vision Agent.
Includes logging, file management, and validation helpers.
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def setup_logging(verbose: bool = False):
    """
    Configure rich console logging.
    
    Args:
        verbose: Enable verbose debug output
    """
    if verbose:
        console.print("[dim]Verbose logging enabled[/dim]")


def ensure_directories(*paths: Path):
    """
    Create directories if they don't exist.
    
    Args:
        *paths: Path objects to create
    """
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def validate_user_data(data: dict) -> tuple[bool, list]:
    """
    Validate that user.json has required fields.
    
    Args:
        data: Parsed user data dictionary
        
    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []
    required_fields = [
        ('personal_info.first_name', 'First name'),
        ('personal_info.last_name', 'Last name'),
        ('personal_info.email', 'Email'),
    ]
    
    for field_path, display_name in required_fields:
        parts = field_path.split('.')
        current = data
        try:
            for part in parts:
                current = current[part]
            if not current:
                errors.append(f"{display_name} is empty")
        except (KeyError, TypeError):
            errors.append(f"{display_name} is missing")
    
    # Validate email format
    email = data.get('personal_info', {}).get('email', '')
    if email and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
        errors.append("Email format is invalid")
    
    return len(errors) == 0, errors


def load_user_data(path: Path) -> Optional[dict]:
    """
    Load and validate user data from JSON file.
    
    Args:
        path: Path to user.json
        
    Returns:
        Parsed user data or None if invalid
    """
    if not path.exists():
        console.print(f"[red]✗ User data file not found: {path}[/red]")
        return None
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        is_valid, errors = validate_user_data(data)
        if not is_valid:
            console.print("[red]✗ User data validation failed:[/red]")
            for error in errors:
                console.print(f"  • {error}")
            return None
        
        console.print("[green]✓ User data loaded successfully[/green]")
        return data
        
    except json.JSONDecodeError as e:
        console.print(f"[red]✗ Invalid JSON in user data: {e}[/red]")
        return None


def cleanup_screenshots(directory: Path, keep_last: int = 5):
    """
    Remove old screenshot files, keeping only the most recent.
    
    Args:
        directory: Screenshots directory
        keep_last: Number of recent screenshots to keep
    """
    if not directory.exists():
        return
    
    screenshots = sorted(
        directory.glob('*.jpg'),
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )
    
    for screenshot in screenshots[keep_last:]:
        try:
            screenshot.unlink()
        except Exception:
            pass


def get_timestamp() -> str:
    """Get formatted timestamp for filenames."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def print_action_summary(action: dict):
    """
    Pretty print an action decision from GPT-4o.
    
    Args:
        action: The action dictionary from GPT-4o response
    """
    table = Table(title="AI Decision", show_header=False, border_style="blue")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("Action Type", action.get('type', 'unknown'))
    table.add_row("Target", action.get('target_label', action.get('element_id', 'N/A')))
    if action.get('value'):
        display_value = action['value'][:50] + '...' if len(str(action['value'])) > 50 else action['value']
        table.add_row("Value", str(display_value))
    table.add_row("Confidence", f"{action.get('confidence', 0):.0%}")
    
    console.print(table)


def print_status_panel(status: str, page_state: str, reasoning: str):
    """
    Print a status panel with current state information.
    
    Args:
        status: Current status (processing/completed/error)
        page_state: Description of current page
        reasoning: AI's reasoning for the action
    """
    color = {
        'processing': 'blue',
        'completed': 'green',
        'error': 'red'
    }.get(status, 'white')
    
    content = f"[bold]Page State:[/bold] {page_state}\n\n[bold]Reasoning:[/bold] {reasoning}"
    console.print(Panel(content, title=f"Status: {status.upper()}", border_style=color))


def format_user_data_for_prompt(user_data: dict) -> str:
    """
    Format user data as a concise string for GPT-4o prompts.
    Reduces token usage by only including essential fields.
    
    Args:
        user_data: Full user data dictionary
        
    Returns:
        Condensed string representation
    """
    personal = user_data.get('personal_info', {})
    links = user_data.get('professional_links', {})
    work_auth = user_data.get('work_authorization', {})
    prefs = user_data.get('preferences', {})
    
    # Build condensed representation
    condensed = {
        'name': f"{personal.get('first_name', '')} {personal.get('last_name', '')}".strip(),
        'email': personal.get('email', ''),
        'phone': personal.get('phone', ''),
        'location': f"{personal.get('address', {}).get('city', '')}, {personal.get('address', {}).get('state', '')}",
        'linkedin': links.get('linkedin', ''),
        'github': links.get('github', ''),
        'portfolio': links.get('portfolio', ''),
        'authorized_to_work': work_auth.get('authorized_to_work', True),
        'needs_sponsorship': work_auth.get('requires_sponsorship', False),
        'willing_to_relocate': work_auth.get('willing_to_relocate', True),
        'salary_expectation': prefs.get('salary_expectation', ''),
        'notice_period': prefs.get('notice_period', ''),
        'start_date': prefs.get('available_start_date', 'Immediately'),
        'how_did_you_hear': prefs.get('how_did_you_hear', 'LinkedIn'),
        'preferred_work_type': prefs.get('preferred_work_type', 'Remote'),
    }
    
    # Add education (just the most recent)
    education = user_data.get('education', [])
    if education:
        ed = education[0]
        condensed['education'] = f"{ed.get('degree', '')} in {ed.get('field_of_study', '')} from {ed.get('institution', '')} ({ed.get('graduation_year', '')})"
    
    # Add current/recent work experience
    experience = user_data.get('work_experience', [])
    if experience:
        exp = experience[0]
        condensed['current_role'] = f"{exp.get('title', '')} at {exp.get('company', '')} ({exp.get('start_date', '')} - {exp.get('end_date', '')})"
    
    # Add skills summary
    skills = user_data.get('skills', {})
    all_skills = []
    for skill_list in skills.values():
        if isinstance(skill_list, list):
            all_skills.extend(skill_list[:3])  # Max 3 from each category
    condensed['key_skills'] = ', '.join(all_skills[:10])  # Max 10 total
    
    # Add common question answers
    common_q = user_data.get('common_questions', {})
    if common_q:
        condensed['prepared_answers'] = common_q
    
    # Add diversity/demographic info
    diversity = user_data.get('diversity_info', {})
    if diversity:
        condensed['pronouns'] = diversity.get('pronouns', '')
        condensed['gender'] = diversity.get('gender', '')
        condensed['ethnicity'] = diversity.get('ethnicity', '')
        condensed['veteran_status'] = diversity.get('veteran_status', '')
        condensed['disability_status'] = diversity.get('disability_status', '')
    
    # Add cover letter if present
    if user_data.get('cover_letter'):
        condensed['cover_letter'] = user_data['cover_letter']
    
    return json.dumps(condensed, indent=2)


def extract_json_from_response(text: str) -> Optional[dict]:
    """
    Extract JSON from GPT response that might have extra text.
    
    Args:
        text: Raw response text
        
    Returns:
        Parsed JSON dict or None
    """
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try to find JSON block
    patterns = [
        r'```json\s*(.*?)\s*```',  # Markdown code block
        r'```\s*(.*?)\s*```',       # Plain code block
        r'\{.*\}',                   # Raw JSON object
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1) if '```' in pattern else match.group(0))
            except json.JSONDecodeError:
                continue
    
    return None
