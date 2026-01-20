"""
Checkbox Handler - Handles checkbox interactions.
"""

import time
from playwright.sync_api import Page
from .base import BaseHandler, scroll_element_into_view


class CheckboxHandler(BaseHandler):
    """
    Handler for checkbox elements.
    Enhanced to handle hidden inputs and custom switches.
    """
    
    def check(self, action: dict) -> bool:
        target_label = action.get('target_label', '')
        target_lower = self._normalize_label(target_label)
        
        locators = [
            # 1. Standard Role
            self.page.get_by_role("checkbox", name=target_label),
            # 2. Label match
            self.page.get_by_label(target_label, exact=False),
            # 3. Input by Name/ID
            self.page.locator(f'input[type="checkbox"][name*="{target_lower}"]'),
            self.page.locator(f'input[type="checkbox"][id*="{target_lower}"]'),
            # 4. ROBUST: Label containing checkbox
            self.page.locator(f'label:has-text("{target_label}")'),
            # 5. Custom UI (Switch/Div)
            self.page.locator(f'[role="checkbox"]:has-text("{target_label}")'),
            self.page.locator(f'[role="switch"]:has-text("{target_label}")'),
        ]
        
        def check_action(element):
            try:
                scroll_element_into_view(self.page, element)
                
                # Check current state if possible
                try:
                    if element.is_checked():
                        return True # Already checked
                except:
                    pass

                # Force click
                element.click(force=True, timeout=1000)
                return True
            except Exception:
                # JS Click fallback
                try:
                    element.evaluate("el => el.click()")
                    return True
                except:
                    return False
        
        if self._try_locators(locators, check_action):
            self._log_success("Checked", target_label)
            return True
        
        # JS Fallback
        if self._check_with_js(target_label):
            return True
        
        self._log_warning(f"Could not check: {target_label}")
        return False
    
    def _check_with_js(self, target_label: str) -> bool:
        try:
            js_result = self.page.evaluate(f'''
                () => {{
                    // Search all labels
                    const labels = document.querySelectorAll('label');
                    for (const label of labels) {{
                        if (label.textContent.toLowerCase().includes("{target_label.lower()}")) {{
                            // Find associated input
                            const checkbox = label.querySelector('input[type="checkbox"]') || 
                                            document.getElementById(label.getAttribute('for'));
                            
                            if (checkbox) {{
                                if (!checkbox.checked) {{
                                    checkbox.click();
                                }}
                                return true;
                            }}
                            // Click label as fallback
                            label.click();
                            return true;
                        }}
                    }}
                    return false;
                }}
            ''')
            if js_result:
                self._log_success("Checked", target_label, "JS fallback")
                return True
        except Exception:
            pass
        return False
