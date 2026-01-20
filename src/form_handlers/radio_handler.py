"""
Radio Handler - Handles radio button selections.
"""

import time
from playwright.sync_api import Page
from .base import BaseHandler, scroll_element_into_view


class RadioHandler(BaseHandler):
    """
    Handler for radio button elements.
    Enhanced to handle hidden inputs and custom styled radios.
    """
    
    def select(self, action: dict) -> bool:
        target_label = action.get('target_label', '')
        value = action.get('value', '')
        
        if not value:
            value = target_label
        
        # Strategies to find the radio button
        locators = [
            # 1. Standard Role
            self.page.get_by_role("radio", name=value),
            # 2. Label exact match
            self.page.get_by_label(value, exact=True),
            # 3. Input value match
            self.page.locator(f'input[type="radio"][value="{value}"]'),
            # 4. ROBUST: Label containing input
            self.page.locator(f'label:has(input[value="{value}"])'),
            # 5. ROBUST: Div/Span container acting as radio
            self.page.locator(f'div[role="radio"]:has-text("{value}")'),
            self.page.locator(f'span[role="radio"]:has-text("{value}")'),
            # 6. Text match (risky but effective)
            self.page.locator(f'label:has-text("{value}")'),
        ]
        
        def select_action(element):
            try:
                scroll_element_into_view(self.page, element)
                # Try force click first
                element.click(force=True, timeout=1000)
                return True
            except Exception:
                # If blocked, use JS click directly on the element
                try:
                    element.evaluate("el => el.click()")
                    return True
                except:
                    return False
        
        if self._try_locators(locators, select_action):
            self._log_success("Selected radio", value)
            return True
        
        # JS Fallback: Search by text content
        if self._select_with_js(value):
            return True
        
        self._log_warning(f"Could not find radio option: {value}")
        return False
    
    def _select_with_js(self, value: str) -> bool:
        try:
            js_result = self.page.evaluate(f'''
                () => {{
                    // Helper to click
                    const clickEl = (el) => {{
                        el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        el.click();
                        return true;
                    }};

                    // 1. Search labels
                    const labels = document.querySelectorAll('label, div[role="radio"], span[role="radio"]');
                    for (const label of labels) {{
                        if (label.textContent.trim().toLowerCase() === "{value.lower()}") {{
                            return clickEl(label);
                        }}
                    }}
                    
                    // 2. Search inputs by value
                    const inputs = document.querySelectorAll('input[type="radio"]');
                    for (const input of inputs) {{
                        if (input.value.toLowerCase() === "{value.lower()}") {{
                            // Try clicking parent label if input is hidden
                            if (input.offsetParent === null && input.parentElement) {{
                                return clickEl(input.parentElement);
                            }}
                            return clickEl(input);
                        }}
                    }}
                    return false;
                }}
            ''')
            if js_result:
                self._log_success("Selected radio", value, "JS fallback")
                return True
        except Exception:
            pass
        return False
