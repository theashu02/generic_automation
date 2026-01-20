"""
Base Handler - Common utilities and base class for all form handlers.
"""

import time
from typing import Optional, List, Callable
from playwright.sync_api import Page, Locator
from rich.console import Console

console = Console()


def scroll_element_into_view(page: Page, locator: Locator) -> bool:
    """
    Scroll an element into view before interacting with it.
    
    Args:
        page: Playwright page object
        locator: Playwright locator for the element
        
    Returns:
        True if element is now visible
    """
    try:
        if locator.count() > 0:
            locator.first.scroll_into_view_if_needed()
            time.sleep(0.3)
            return True
    except Exception:
        pass
    return False


def wait_for_element(locator: Locator, timeout: float = 5.0) -> bool:
    """
    Wait for an element to become visible.
    
    Args:
        locator: Playwright locator
        timeout: Maximum wait time in seconds
        
    Returns:
        True if element became visible
    """
    try:
        locator.first.wait_for(state="visible", timeout=timeout * 1000)
        return True
    except Exception:
        return False


class BaseHandler:
    """
    Base class for all form element handlers.
    
    Provides common functionality for element location,
    scrolling, and fallback strategies.
    """
    
    def __init__(self, page: Page):
        """
        Initialize handler with Playwright page.
        
        Args:
            page: Playwright Page object
        """
        self.page = page
    
    def _try_locators(
        self, 
        locators: List[Locator], 
        action: Callable[[Locator], bool],
        scroll_retry: bool = True
    ) -> bool:
        """
        Try multiple locator strategies until one succeeds.
        
        Args:
            locators: List of Playwright locators to try
            action: Function to call on successful locator
            scroll_retry: If True, scroll and retry on first failure
            
        Returns:
            True if any locator succeeded
        """
        # First pass - try all locators
        for locator in locators:
            try:
                if locator.count() > 0:
                    scroll_element_into_view(self.page, locator)
                    if locator.first.is_visible():
                        if action(locator.first):
                            return True
            except Exception:
                continue
        
        # Second pass - scroll down and retry
        if scroll_retry:
            self.page.mouse.wheel(0, 400)
            time.sleep(0.5)
            
            for locator in locators:
                try:
                    if locator.count() > 0:
                        scroll_element_into_view(self.page, locator)
                        if locator.first.is_visible():
                            if action(locator.first):
                                return True
                except Exception:
                    continue
        
        return False
    
    def _normalize_label(self, label: str) -> str:
        """
        Normalize a label for matching.
        
        Args:
            label: Original label text
            
        Returns:
            Normalized version (lowercase, no spaces)
        """
        return label.lower().replace(" ", "").replace("-", "").replace("_", "")
    
    def _log_success(self, action: str, target: str, method: str = ""):
        """Log successful action."""
        method_str = f" ({method})" if method else ""
        console.print(f"[green]✓ {action} '{target}'{method_str}[/green]")
    
    def _log_warning(self, message: str):
        """Log warning message."""
        console.print(f"[yellow]⚠ {message}[/yellow]")
    
    def _log_debug(self, message: str):
        """Log debug message."""
        console.print(f"[dim]{message}[/dim]")
