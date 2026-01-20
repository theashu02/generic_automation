"""
Input Handler - Handles text inputs, textareas, and autocomplete suggestions.
"""

import time
from typing import Optional
from playwright.sync_api import Page
from .base import BaseHandler, scroll_element_into_view


class InputHandler(BaseHandler):
    """
    Handler for text input fields and textareas.
    
    Supports:
    - Standard text inputs
    - Textareas (cover letters, descriptions)
    - Autocomplete/Suggestion dropdowns (e.g., Location, Company)
    - Email, phone, URL inputs
    """
    
    def __init__(self, page: Page, cover_letter_text: Optional[str] = None):
        """
        Initialize input handler.
        
        Args:
            page: Playwright Page object
            cover_letter_text: Pre-loaded cover letter text
        """
        super().__init__(page)
        self.cover_letter_text = cover_letter_text
    
    def fill(self, action: dict) -> bool:
        """
        Fill a text input or textarea and handle suggestions if they appear.
        
        Args:
            action: Action dict with target_label and value
            
        Returns:
            True if successful
        """
        target_label = action.get('target_label', '')
        value = action.get('value', '')
        
        # Check if this is a cover letter field
        if self._is_cover_letter_field(target_label) and self.cover_letter_text:
            value = self.cover_letter_text
            self._log_debug("Using loaded cover letter text")
        
        target_lower = self._normalize_label(target_label)
        
        # Build locator strategies in priority order
        locators = [
            # Strategy 1: Role-based textbox
            self.page.get_by_role("textbox", name=target_label),
            # Strategy 2: By label association
            self.page.get_by_label(target_label),
            # Strategy 3: By placeholder
            self.page.get_by_placeholder(target_label),
            # Strategy 4: Textarea by name/id
            self.page.locator(f'textarea[name*="{target_lower}"]'),
            self.page.locator(f'textarea[id*="{target_lower}"]'),
            # Strategy 5: Input by name/id  
            self.page.locator(f'input[name*="{target_lower}"]'),
            self.page.locator(f'input[id*="{target_lower}"]'),
            # Strategy 6: Aria-label
            self.page.locator(f'[aria-label*="{target_label}" i]'),
            # Strategy 7: Adjacent to label (Robust for modern frameworks)
            self.page.locator(f'label:has-text("{target_label}") + input'),
            self.page.locator(f'label:has-text("{target_label}") + textarea'),
            self.page.locator(f'label:has-text("{target_label}") ~ input'),
            self.page.locator(f'label:has-text("{target_label}") ~ div input'),
            self.page.locator(f'div:has-text("{target_label}") input'),
        ]
        
        # Add cover-letter specific locators
        if self._is_cover_letter_field(target_label):
            locators.extend([
                self.page.locator('textarea[name*="cover"]'),
                self.page.locator('textarea#cover_letter'),
                self.page.locator('textarea[data-field*="cover"]'),
                self.page.locator('textarea[placeholder*="cover" i]'),
            ])
        
        # Try each locator
        filled = False
        for locator in locators:
            try:
                if locator.count() > 0:
                    scroll_element_into_view(self.page, locator)
                    if locator.first.is_visible():
                        # Clear and fill
                        locator.first.fill("")
                        time.sleep(0.1)
                        locator.first.fill(value)
                        filled = True
                        break
            except Exception:
                continue

        # Last resort for cover letter
        if not filled and self._is_cover_letter_field(target_label):
            try:
                textareas = self.page.locator('textarea:visible')
                if textareas.count() > 0:
                    textareas.first.fill(value)
                    self._log_success("Filled", "textarea", "cover letter fallback")
                    filled = True
            except Exception:
                pass
        
        # JavaScript fallback
        if not filled:
            if self._fill_with_js(target_label, value):
                filled = True
        
        if filled:
            display_value = value[:40] + "..." if len(value) > 40 else value
            self._log_success("Filled", target_label, f"value={display_value}")
            
            # Check for autocomplete suggestions (NEW)
            self._check_for_suggestions(value)
            return True
            
        self._log_warning(f"Could not find input: {target_label}")
        return False
    
    def _check_for_suggestions(self, value: str):
        """
        Check if typing triggered a suggestion dropdown and select the matching option.
        """
        # Wait briefly for network/animation
        time.sleep(0.8)
        
        # Common selectors for suggestion containers
        suggestion_selectors = [
            '[role="listbox"]', 
            '.pac-container',  # Google Maps
            '.ui-menu',        # jQuery UI
            '.dropdown-menu',  # Bootstrap
            'div[class*="suggestions"]',
            'div[class*="results"]',
            'div[class*="option-list"]',
            'ul[class*="list"]'
        ]
        
        # Look for any visible suggestion box
        for selector in suggestion_selectors:
            try:
                box = self.page.locator(f'{selector}:visible').first
                if box.count() > 0:
                    # 1. Try exact match in the list
                    option = box.locator(f'text="{value}"').first
                    if option.count() > 0 and option.is_visible():
                        option.click(force=True)
                        self._log_success("Selected suggestion", value, "exact match")
                        return

                    # 2. Try partial match
                    option = box.locator(f'text={value}').first
                    if option.count() > 0 and option.is_visible():
                        option.click(force=True)
                        self._log_success("Selected suggestion", value, "partial match")
                        return
                    
                    # 3. Fallback: Click the first option (often "Best Match")
                    first_option = box.locator('[role="option"], li, .pac-item').first
                    if first_option.count() > 0 and first_option.is_visible():
                        first_option.click(force=True)
                        self._log_debug(f"Clicked first suggestion for {value}")
                        return
            except Exception:
                pass

    def _is_cover_letter_field(self, label: str) -> bool:
        """Check if the field is for cover letter."""
        label_lower = label.lower()
        return 'cover' in label_lower and 'letter' in label_lower
    
    def _fill_with_js(self, target_label: str, value: str) -> bool:
        """Try to fill using JavaScript as fallback."""
        try:
            js_result = self.page.evaluate(f'''
                () => {{
                    const labels = document.querySelectorAll('label');
                    for (const label of labels) {{
                        if (label.textContent.toLowerCase().includes("{target_label.lower()}")) {{
                            const forAttr = label.getAttribute('for');
                            let input = forAttr ? document.getElementById(forAttr) : null;
                            if (!input) {{
                                input = label.querySelector('input, textarea');
                            }}
                            if (!input) {{
                                input = label.nextElementSibling;
                            }}
                            if (input && (input.tagName === 'INPUT' || input.tagName === 'TEXTAREA')) {{
                                input.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                                input.focus();
                                input.value = `{value.replace('`', '\\`').replace('\\n', '\\\\n')}`;
                                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                return true;
                            }}
                        }}
                    }}
                    return false;
                }}
            ''')
            if js_result:
                self._log_success("Filled", target_label, "JS fallback")
                return True
        except Exception as e:
            self._log_debug(f"JS fill fallback failed: {e}")
        
        return False
