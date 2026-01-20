"""
Dropdown Handler - Handles native and custom dropdowns.
"""

import time
from typing import Literal, Optional
from playwright.sync_api import Page
from .base import BaseHandler, scroll_element_into_view


class DropdownHandler(BaseHandler):
    """
    Handler for dropdown/select elements.
    
    Supports:
    - Native HTML <select> elements
    - Custom dropdown UIs (React-Select, Material UI, Ant Design, etc.)
    - Combobox patterns (role="combobox")
    - Listbox patterns (role="listbox")
    """
    
    def select(self, action: dict) -> bool:
        """
        Select an option from a dropdown.
        
        Args:
            action: Action dict with target_label and value
            
        Returns:
            True if successful
        """
        target_label = action.get('target_label', '')
        value = action.get('value', '')
        target_lower = self._normalize_label(target_label)
        
        # First, try native <select> elements
        if self._handle_native_select(target_label, target_lower, value):
            return True
        
        # Handle custom dropdown
        if self._handle_custom_dropdown(target_label, target_lower, value):
            return True
        
        self._log_warning(f"Could not select '{value}' in '{target_label}'")
        return False
    
    def _handle_native_select(self, target_label: str, target_lower: str, value: str) -> bool:
        """
        Handle native <select> elements.
        
        Returns:
            True if native select was found and used successfully
        """
        native_locators = [
            self.page.locator(f'select[name*="{target_lower}"]'),
            self.page.locator(f'select[id*="{target_lower}"]'),
            self.page.get_by_label(target_label).locator('select'),
            self.page.locator(f'label:has-text("{target_label}") + select'),
            self.page.locator(f'label:has-text("{target_label}") ~ select'),
        ]
        
        for locator in native_locators:
            try:
                if locator.count() > 0:
                    scroll_element_into_view(self.page, locator)
                    if locator.first.is_visible():
                        # Try by label first, then by value
                        try:
                            locator.first.select_option(label=value)
                            self._log_success("Selected", value, f"native dropdown '{target_label}'")
                            return True
                        except Exception:
                            pass
                        try:
                            locator.first.select_option(value=value)
                            self._log_success("Selected", value, f"native dropdown '{target_label}'")
                            return True
                        except Exception:
                            pass
                        # Try partial match
                        try:
                            locator.first.select_option(label=value, timeout=1000)
                            return True
                        except Exception:
                            pass
            except Exception:
                continue
        
        return False
    
    def _handle_custom_dropdown(self, target_label: str, target_lower: str, value: str) -> bool:
        """
        Handle custom dropdown components.
        
        Returns:
            True if custom dropdown was handled successfully
        """
        self._log_debug(f"Trying custom dropdown for '{target_label}'...")
        
        # Step 1: Find and click the dropdown trigger
        dropdown_triggers = [
            self.page.get_by_role("combobox", name=target_label),
            self.page.get_by_label(target_label),
            self.page.locator(f'[aria-label*="{target_label}"]'),
            self.page.locator(f'[data-testid*="{target_lower}"]'),
            # Common custom dropdown patterns
            self.page.locator(f'div:has-text("{target_label}") >> button'),
            self.page.locator(f'div:has-text("{target_label}") >> [role="button"]'),
            self.page.locator(f'label:has-text("{target_label}") + div'),
            self.page.locator(f'label:has-text("{target_label}") ~ div >> button'),
            self.page.locator(f'label:has-text("{target_label}") ~ div [role="combobox"]'),
            self.page.locator(f'label:has-text("{target_label}") ~ div'),
            # Common class patterns
            self.page.locator(f'[class*="select"]:has-text("{target_label}")'),
            self.page.locator(f'[class*="dropdown"]:has-text("{target_label}")'),
            # React-Select, MUI, Ant Design patterns
            self.page.locator(f'.select__control:has-text("{target_label}")'),
            self.page.locator(f'.MuiSelect-root:has-text("{target_label}")'),
            self.page.locator(f'.ant-select:has-text("{target_label}")'),
        ]
        
        dropdown_opened = False
        for trigger in dropdown_triggers:
            try:
                if trigger.count() > 0:
                    scroll_element_into_view(self.page, trigger)
                    if trigger.first.is_visible():
                        trigger.first.click(force=True)
                        time.sleep(0.5)  # Wait for dropdown animation
                        dropdown_opened = True
                        self._log_debug(f"Opened dropdown '{target_label}'")
                        break
            except Exception:
                continue
        
        if not dropdown_opened:
            # Scroll and retry
            self.page.mouse.wheel(0, 300)
            time.sleep(0.3)
            
            for trigger in dropdown_triggers:
                try:
                    if trigger.count() > 0:
                        scroll_element_into_view(self.page, trigger)
                        if trigger.first.is_visible():
                            trigger.first.click(force=True)
                            time.sleep(0.5)
                            dropdown_opened = True
                            break
                except Exception:
                    continue
        
        # Step 2: Click on the option
        time.sleep(0.3)  # Brief wait for options to render
        
        option_locators = [
            # Exact match first
            self.page.get_by_role("option", name=value),
            self.page.get_by_role("menuitem", name=value),
            self.page.get_by_role("listitem").filter(has_text=value),
            self.page.locator(f'[role="option"]:has-text("{value}")'),
            self.page.locator(f'[role="menuitem"]:has-text("{value}")'),
            self.page.locator(f'li:has-text("{value}")'),
            # Data attributes
            self.page.locator(f'[data-value="{value}"]'),
            self.page.locator(f'[data-value="{value.lower()}"]'),
            # Listbox options
            self.page.locator(f'div[role="listbox"] >> text="{value}"'),
            self.page.locator(f'ul >> li:has-text("{value}")'),
            # Framework-specific
            self.page.locator(f'.select__option:has-text("{value}")'),
            self.page.locator(f'.MuiMenuItem-root:has-text("{value}")'),
            self.page.locator(f'.ant-select-item:has-text("{value}")'),
            # Text match as last resort
            self.page.get_by_text(value, exact=True),
        ]
        
        for option in option_locators:
            try:
                if option.count() > 0 and option.first.is_visible():
                    option.first.click(force=True)
                    time.sleep(0.2)
                    self._log_success("Selected", value, f"custom dropdown '{target_label}'")
                    return True
            except Exception:
                continue
        
        # Final fallback: click any visible element containing the value
        try:
            visible_options = self.page.locator(f':visible:has-text("{value}")')
            if visible_options.count() > 0:
                visible_options.last.click()
                self._log_success("Selected", value, "visible text fallback")
                return True
        except Exception:
            pass
        
        return False
