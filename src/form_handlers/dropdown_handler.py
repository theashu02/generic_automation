"""
Dropdown Handler - Handles native and custom dropdowns.
Enhanced with global option search for React Portals.
"""

import time
from playwright.sync_api import Page
from .base import BaseHandler, scroll_element_into_view


class DropdownHandler(BaseHandler):
    """
    Handler for dropdown/select elements.
    Supports native <select> and custom React/MUI/AntD dropdowns.
    """
    
    def select(self, action: dict) -> bool:
        target_label = action.get('target_label', '')
        value = action.get('value', '')
        target_lower = self._normalize_label(target_label)
        value_lower = value.lower().strip()
        
        # 1. Try native <select>
        if self._handle_native_select(target_label, target_lower, value):
            return True
        
        # 2. Handle custom dropdown
        if self._handle_custom_dropdown(target_label, target_lower, value, value_lower):
            return True
        
        # 3. Keyboard fallback
        if self._handle_keyboard_select(target_label, value):
            return True
        
        self._log_warning(f"Could not select '{value}' in '{target_label}'")
        return False
    
    def _handle_native_select(self, target_label: str, target_lower: str, value: str) -> bool:
        native_locators = [
            self.page.locator(f'select[name*="{target_lower}"]'),
            self.page.locator(f'select[id*="{target_lower}"]'),
            self.page.get_by_label(target_label).locator('select'),
            self.page.locator(f'label:has-text("{target_label}") + select'),
            self.page.locator(f'label:has-text("{target_label}") ~ select'),
            self.page.locator('select').filter(has=self.page.locator(f'option:has-text("{value}")')),
        ]
        
        for locator in native_locators:
            try:
                if locator.count() > 0:
                    scroll_element_into_view(self.page, locator)
                    if locator.first.is_visible():
                        try:
                            locator.first.select_option(label=value)
                            self._log_success("Selected", value, f"native dropdown '{target_label}'")
                            return True
                        except:
                            pass
                        try:
                            locator.first.select_option(value=value)
                            self._log_success("Selected", value, f"native dropdown '{target_label}'")
                            return True
                        except:
                            pass
            except Exception:
                continue
        return False
    
    def _handle_custom_dropdown(self, target_label: str, target_lower: str, value: str, value_lower: str) -> bool:
        self._log_debug(f"Trying custom dropdown for '{target_label}'...")
        
        # Find trigger
        dropdown_triggers = [
            self.page.get_by_role("combobox", name=target_label),
            self.page.get_by_label(target_label),
            self.page.locator(f'[aria-label*="{target_label}" i]'),
            self.page.locator(f'div:has-text("{target_label}") >> [role="button"]').first,
            self.page.locator(f'label:has-text("{target_label}") ~ div >> [role="combobox"]'),
            self.page.locator(f'.select__control:has-text("{target_label}")'), # React-Select
            self.page.locator(f'.MuiSelect-root:has-text("{target_label}")'), # MUI
            self.page.locator(f'.ant-select-selector:has-text("{target_label}")'), # AntD
            self.page.locator(f'div:has-text("{target_label}")').last, # Generic
        ]
        
        dropdown_opened = False
        
        for trigger in dropdown_triggers:
            try:
                if trigger.count() > 0:
                    scroll_element_into_view(self.page, trigger)
                    if trigger.first.is_visible():
                        trigger.first.click(force=True)
                        time.sleep(0.5) # Wait for animation
                        dropdown_opened = True
                        break
            except Exception:
                continue
        
        if not dropdown_opened:
            # Retry with scroll
            self.page.mouse.wheel(0, 300)
            time.sleep(0.3)
            for trigger in dropdown_triggers:
                try:
                    if trigger.count() > 0 and trigger.first.is_visible():
                        trigger.first.click(force=True)
                        time.sleep(0.5)
                        dropdown_opened = True
                        break
                except:
                    continue

        # Look for option globally (React Portals)
        if self._click_option(value, value_lower, target_label):
            return True
            
        return False
    
    def _click_option(self, value: str, value_lower: str, target_label: str) -> bool:
        """Search globally for the option and click it."""
        
        # Priority: Exact match -> Partial match
        option_locators = [
            # High confidence: Role + Exact Text
            self.page.get_by_role("option", name=value, exact=True),
            self.page.get_by_text(value, exact=True),
            
            # Medium confidence: Role + Contains Text
            self.page.locator(f'[role="option"]:has-text("{value}")'),
            self.page.locator(f'[role="menuitem"]:has-text("{value}")'),
            self.page.locator(f'li:has-text("{value}")'),
            
            # Framework specific
            self.page.locator(f'.select__option:has-text("{value}")'), # React-Select
            self.page.locator(f'.MuiMenuItem-root:has-text("{value}")'), # MUI
            self.page.locator(f'.ant-select-item-option-content:has-text("{value}")'), # AntD
            
            # Generic
            self.page.locator(f'div[id*="option"]:has-text("{value}")'),
            self.page.locator(f'div:has-text("{value}")'),
        ]
        
        for locator in option_locators:
            try:
                # Iterate all matches (some might be hidden/duplicates)
                count = locator.count()
                for i in range(min(count, 10)): # Check first 10 matches
                    element = locator.nth(i)
                    if element.is_visible():
                        element.scroll_into_view_if_needed()
                        element.click(force=True)
                        self._log_success("Selected", value, f"dropdown '{target_label}'")
                        return True
            except Exception:
                continue
                
        return False

    def _handle_keyboard_select(self, target_label: str, value: str) -> bool:
        try:
            field = self.page.get_by_label(target_label)
            if field.count() > 0:
                field.first.click()
                time.sleep(0.2)
                self.page.keyboard.type(value, delay=50)
                time.sleep(0.5)
                self.page.keyboard.press("Enter")
                self._log_success("Selected", value, "keyboard navigation")
                return True
        except:
            pass
        return False
