"""
Radio Handler - Handles radio button selections.
"""

import time
from playwright.sync_api import Page
from .base import BaseHandler, scroll_element_into_view


class RadioHandler(BaseHandler):
    """
    Handler for radio button elements.
    
    Supports:
    - Native HTML radio buttons
    - Custom styled radio buttons
    - "How did you hear about us?" questions
    - Yes/No toggles
    - Segmented controls
    """
    
    def select(self, action: dict) -> bool:
        """
        Select a radio button option.
        
        Args:
            action: Action dict with target_label (question) and value (option)
            
        Returns:
            True if successful
        """
        target_label = action.get('target_label', '')
        value = action.get('value', '')
        
        # The value is the option text to select
        if not value:
            value = target_label  # Sometimes the target_label IS the value
        
        # Build locator strategies - focus on the VALUE (option text)
        locators = [
            # Strategy 1: Role-based radio with option name
            self.page.get_by_role("radio", name=value),
            # Strategy 2: Label matching the value
            self.page.get_by_label(value, exact=True),
            self.page.get_by_label(value, exact=False),
            # Strategy 3: Radio by value attribute
            self.page.locator(f'input[type="radio"][value="{value}"]'),
            self.page.locator(f'input[type="radio"][value="{value.lower()}"]'),
            self.page.locator(f'input[type="radio"][value*="{self._normalize_label(value)}"]'),
            # Strategy 4: Radio within label containing value
            self.page.locator(f'label:has-text("{value}") input[type="radio"]'),
            self.page.locator(f'label:has-text("{value}")'),
            # Strategy 5: Custom radiogroup
            self.page.locator(f'[role="radiogroup"] >> text="{value}"'),
            self.page.locator(f'[role="radio"]:has-text("{value}")'),
            # Strategy 6: Radio in container with value text
            self.page.locator(f'div:has-text("{value}") >> input[type="radio"]'),
            self.page.locator(f'span:has-text("{value}")'),
        ]
        
        # Try force click (works better with custom UIs)
        def select_action(element):
            try:
                element.click(force=True)
                time.sleep(0.2)
                return True
            except Exception:
                pass
            try:
                element.click()
                return True
            except Exception:
                return False
        
        if self._try_locators(locators, select_action):
            self._log_success("Selected radio", value)
            return True
        
        # Try clicking exact text match
        try:
            option_text = self.page.get_by_text(value, exact=True)
            if option_text.count() > 0:
                scroll_element_into_view(self.page, option_text)
                option_text.first.click(force=True)
                time.sleep(0.2)
                self._log_success("Selected radio", value, "text click")
                return True
        except Exception:
            pass
        
        # Try partial match
        try:
            option_text = self.page.get_by_text(value, exact=False)
            if option_text.count() > 0:
                for i in range(min(5, option_text.count())):
                    try:
                        el = option_text.nth(i)
                        if el.is_visible():
                            el.click(force=True)
                            time.sleep(0.2)
                            self._log_success("Selected radio", value, "partial text")
                            return True
                    except Exception:
                        continue
        except Exception:
            pass
        
        # JavaScript fallback
        if self._select_with_js(value):
            return True
        
        self._log_warning(f"Could not find radio option: {value}")
        return False
    
    def _select_with_js(self, value: str) -> bool:
        """
        Try to select radio using JavaScript.
        
        Args:
            value: Option text to select
            
        Returns:
            True if successful
        """
        try:
            js_result = self.page.evaluate(f'''
                () => {{
                    // Find by label text
                    const elements = document.querySelectorAll('label, span, div');
                    for (const el of elements) {{
                        const text = el.textContent.trim().toLowerCase();
                        if (text === "{value.lower()}" || text.includes("{value.lower()}")) {{
                            // Try to find associated radio input
                            const radio = el.querySelector('input[type="radio"]') ||
                                         el.previousElementSibling ||
                                         el.parentElement.querySelector('input[type="radio"]');
                            if (radio && radio.type === 'radio') {{
                                radio.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                                radio.click();
                                return true;
                            }}
                            // Click the element itself
                            el.click();
                            return true;
                        }}
                    }}
                    // Try role="radio"
                    const radios = document.querySelectorAll('[role="radio"]');
                    for (const radio of radios) {{
                        if (radio.textContent.toLowerCase().includes("{value.lower()}")) {{
                            radio.click();
                            return true;
                        }}
                    }}
                    return false;
                }}
            ''')
            if js_result:
                self._log_success("Selected radio", value, "JS fallback")
                return True
        except Exception as e:
            self._log_debug(f"JS radio fallback failed: {e}")
        
        return False
