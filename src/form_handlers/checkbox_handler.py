"""
Checkbox Handler - Handles checkbox interactions.
"""

import time
from playwright.sync_api import Page
from .base import BaseHandler, scroll_element_into_view


class CheckboxHandler(BaseHandler):
    """
    Handler for checkbox elements.
    
    Supports:
    - Native HTML checkboxes
    - Custom styled checkboxes (hidden input + visible div)
    - Toggle switches (role="switch")
    - Terms & conditions checkboxes
    - Multi-select checkbox groups
    """
    
    def check(self, action: dict) -> bool:
        """
        Check a checkbox element.
        
        Args:
            action: Action dict with target_label
            
        Returns:
            True if successful
        """
        target_label = action.get('target_label', '')
        target_lower = self._normalize_label(target_label)
        
        # Build locator strategies
        locators = [
            # Strategy 1: Role-based checkbox
            self.page.get_by_role("checkbox", name=target_label),
            # Strategy 2: By label
            self.page.get_by_label(target_label, exact=False),
            # Strategy 3: Input by name/id
            self.page.locator(f'input[type="checkbox"][name*="{target_lower}"]'),
            self.page.locator(f'input[type="checkbox"][id*="{target_lower}"]'),
            # Strategy 4: Checkbox within label
            self.page.locator(f'label:has-text("{target_label}") input[type="checkbox"]'),
            # Strategy 5: Label itself (click to toggle)
            self.page.locator(f'label:has-text("{target_label}")'),
            # Strategy 6: Custom UI checkbox
            self.page.locator(f'[role="checkbox"]:has-text("{target_label}")'),
            self.page.locator(f'[role="switch"]:has-text("{target_label}")'),
            # Strategy 7: Checkbox in container with text
            self.page.locator(f'div:has-text("{target_label}") input[type="checkbox"]'),
            self.page.locator(f'span:has-text("{target_label}") input[type="checkbox"]'),
        ]
        
        # Try force click first (works better with custom UIs)
        def check_action(element):
            try:
                element.click(force=True)
                time.sleep(0.2)
                return True
            except Exception:
                pass
            
            # Try native check method
            try:
                if hasattr(element, 'is_checked') and not element.is_checked():
                    element.check(force=True)
                    return True
                return True  # Already checked
            except Exception:
                return False
        
        if self._try_locators(locators, check_action):
            self._log_success("Checked", target_label)
            return True
        
        # JavaScript fallback
        if self._check_with_js(target_label):
            return True
        
        self._log_warning(f"Could not check: {target_label}")
        return False
    
    def _check_with_js(self, target_label: str) -> bool:
        """
        Try to check using JavaScript as fallback.
        
        Args:
            target_label: Checkbox label
            
        Returns:
            True if successful
        """
        try:
            js_result = self.page.evaluate(f'''
                () => {{
                    const labels = document.querySelectorAll('label');
                    for (const label of labels) {{
                        if (label.textContent.toLowerCase().includes("{target_label.lower()}")) {{
                            const checkbox = label.querySelector('input[type="checkbox"]') || 
                                            label.previousElementSibling || 
                                            label.nextElementSibling ||
                                            document.getElementById(label.getAttribute('for'));
                            if (checkbox && checkbox.type === 'checkbox') {{
                                checkbox.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                                if (!checkbox.checked) {{
                                    checkbox.click();
                                }}
                                return true;
                            }}
                            // Click label itself
                            label.click();
                            return true;
                        }}
                    }}
                    // Try XPath
                    const el = document.evaluate(
                        '//*[contains(text(), "{target_label}")]', 
                        document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
                    ).singleNodeValue;
                    if (el) {{
                        el.click();
                        return true;
                    }}
                    return false;
                }}
            ''')
            if js_result:
                self._log_success("Checked", target_label, "JS fallback")
                return True
        except Exception as e:
            self._log_debug(f"JS checkbox fallback failed: {e}")
        
        return False
