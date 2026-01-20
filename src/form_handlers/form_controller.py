"""
Form Controller - Unified action router for all form handlers.
"""

import time
from pathlib import Path
from typing import Optional
from playwright.sync_api import Page
from rich.console import Console

from .base import BaseHandler
from .input_handler import InputHandler
from .checkbox_handler import CheckboxHandler
from .radio_handler import RadioHandler
from .dropdown_handler import DropdownHandler
from .file_handler import FileHandler

console = Console()


class FormController:
    """
    Unified controller that routes actions to appropriate handlers.
    
    Usage:
        controller = FormController(page, resume_path, cover_letter_path, cover_letter_text)
        success = controller.execute(action_dict)
    """
    
    def __init__(
        self,
        page: Page,
        resume_path: Optional[Path] = None,
        cover_letter_path: Optional[Path] = None,
        cover_letter_text: Optional[str] = None
    ):
        """
        Initialize form controller with all handlers.
        
        Args:
            page: Playwright Page object
            resume_path: Path to resume file
            cover_letter_path: Path to cover letter file
            cover_letter_text: Cover letter text content
        """
        self.page = page
        
        # Initialize all handlers
        self.input_handler = InputHandler(page, cover_letter_text)
        self.checkbox_handler = CheckboxHandler(page)
        self.radio_handler = RadioHandler(page)
        self.dropdown_handler = DropdownHandler(page)
        self.file_handler = FileHandler(page, resume_path, cover_letter_path)
    
    def execute(self, action: dict) -> bool:
        """
        Execute an action by routing to the appropriate handler.
        
        Args:
            action: Action dictionary with type and parameters
            
        Returns:
            True if action succeeded
        """
        action_type = action.get('type', '')
        
        # Action routing table
        handlers = {
            'fill': self.input_handler.fill,
            'click': self._handle_click,
            'select': self.dropdown_handler.select,
            'check': self.checkbox_handler.check,
            'radio': self.radio_handler.select,
            'upload_resume': self.file_handler.upload_resume,
            'upload_cover_letter': self.file_handler.upload_cover_letter,
            'upload': self.file_handler.upload_file,
            'scroll_down': self._scroll_down,
            'scroll_up': self._scroll_up,
            'wait': self._wait,
        }
        
        handler = handlers.get(action_type)
        if handler:
            try:
                return handler(action)
            except Exception as e:
                console.print(f"[red]✗ Action '{action_type}' failed: {e}[/red]")
                return False
        
        console.print(f"[yellow]⚠ Unknown action type: {action_type}[/yellow]")
        return False
    
    def _handle_click(self, action: dict) -> bool:
        """
        Handle click actions (buttons, links).
        
        Args:
            action: Action dict with target_label
            
        Returns:
            True if successful
        """
        target_label = action.get('target_label', '')
        
        locators = [
            self.page.get_by_role("button", name=target_label),
            self.page.get_by_role("link", name=target_label),
            self.page.get_by_text(target_label, exact=True),
            self.page.get_by_text(target_label),
            self.page.locator(f'[aria-label="{target_label}"]'),
            self.page.locator(f'button:has-text("{target_label}")'),
            self.page.locator(f'a:has-text("{target_label}")'),
            self.page.locator(f'[role="button"]:has-text("{target_label}")'),
        ]
        
        for locator in locators:
            try:
                if locator.count() > 0:
                    from .base import scroll_element_into_view
                    scroll_element_into_view(self.page, locator)
                    if locator.first.is_visible():
                        locator.first.click(force=True)
                        console.print(f"[green]✓ Clicked '{target_label}'[/green]")
                        return True
            except Exception:
                continue
        
        # Scroll down and retry
        self.page.mouse.wheel(0, 400)
        time.sleep(0.5)
        
        for locator in locators:
            try:
                if locator.count() > 0:
                    from .base import scroll_element_into_view
                    scroll_element_into_view(self.page, locator)
                    if locator.first.is_visible():
                        locator.first.click(force=True)
                        console.print(f"[green]✓ Clicked '{target_label}' (after scroll)[/green]")
                        return True
            except Exception:
                continue
        
        # JavaScript fallback
        try:
            js_result = self.page.evaluate(f'''
                () => {{
                    const elements = document.querySelectorAll('button, a, [role="button"], input[type="submit"]');
                    for (const el of elements) {{
                        if (el.textContent.toLowerCase().includes("{target_label.lower()}") ||
                            el.getAttribute('aria-label')?.toLowerCase().includes("{target_label.lower()}")) {{
                            el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                            el.click();
                            return true;
                        }}
                    }}
                    return false;
                }}
            ''')
            if js_result:
                console.print(f"[green]✓ Clicked '{target_label}' (JS fallback)[/green]")
                return True
        except Exception:
            pass
        
        console.print(f"[yellow]⚠ Could not find button/link: {target_label}[/yellow]")
        return False
    
    def _scroll_down(self, action: dict = None) -> bool:
        """Scroll the page down."""
        self.page.mouse.wheel(0, 500)
        console.print("[green]✓ Scrolled down[/green]")
        return True
    
    def _scroll_up(self, action: dict = None) -> bool:
        """Scroll the page up."""
        self.page.mouse.wheel(0, -500)
        console.print("[green]✓ Scrolled up[/green]")
        return True
    
    def _wait(self, action: dict = None) -> bool:
        """Wait for a moment."""
        time.sleep(2)
        console.print("[green]✓ Waited[/green]")
        return True
