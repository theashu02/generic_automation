"""
Element Marker - Set-of-Mark Implementation
Injects JavaScript to overlay numbered markers on interactive elements.
This enables 100% accurate element targeting by referencing numbers instead of selectors.
"""

from playwright.sync_api import Page
from rich.console import Console

console = Console()


class ElementMarker:
    """
    Set-of-Mark implementation for precise element targeting.
    
    Injects JavaScript to draw numbered red boxes over all interactive elements,
    allowing the AI to reference elements by their number ID.
    """
    
    # JavaScript to inject markers onto interactive elements
    MARKER_INJECTION_SCRIPT = """
    () => {
        // Remove any existing markers first
        document.querySelectorAll('.vision-agent-marker').forEach(el => el.remove());
        
        // Find all interactive elements
        const interactiveSelectors = [
            'input:not([type="hidden"])',
            'textarea',
            'select',
            'button',
            '[role="button"]',
            '[role="checkbox"]',
            '[role="radio"]',
            '[role="combobox"]',
            '[role="listbox"]',
            '[role="menuitem"]',
            '[role="option"]',
            '[role="switch"]',
            '[role="tab"]',
            'a[href]',
            '[onclick]',
            '[contenteditable="true"]',
            'label[for]',
            '[tabindex]:not([tabindex="-1"])'
        ];
        
        const elements = document.querySelectorAll(interactiveSelectors.join(', '));
        const markers = [];
        let idCounter = 1;
        
        elements.forEach((el, index) => {
            // Skip hidden or zero-size elements
            const rect = el.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) return;
            if (window.getComputedStyle(el).display === 'none') return;
            if (window.getComputedStyle(el).visibility === 'hidden') return;
            
            // Skip elements outside viewport
            if (rect.bottom < 0 || rect.top > window.innerHeight) return;
            if (rect.right < 0 || rect.left > window.innerWidth) return;
            
            // Create marker container
            const marker = document.createElement('div');
            marker.className = 'vision-agent-marker';
            marker.setAttribute('data-element-id', idCounter);
            
            // Store reference to original element
            el.setAttribute('data-vision-agent-id', idCounter);
            
            // Style the marker (red box with number)
            marker.style.cssText = `
                position: fixed;
                left: ${rect.left - 2}px;
                top: ${rect.top - 2}px;
                width: ${rect.width + 4}px;
                height: ${rect.height + 4}px;
                border: 2px solid #FF0000;
                background: transparent;
                pointer-events: none;
                z-index: 999999;
                box-sizing: border-box;
            `;
            
            // Create the number label
            const label = document.createElement('div');
            label.textContent = idCounter;
            label.style.cssText = `
                position: absolute;
                top: -12px;
                left: -2px;
                background: #FF0000;
                color: white;
                font-size: 10px;
                font-weight: bold;
                padding: 1px 4px;
                border-radius: 2px;
                font-family: Arial, sans-serif;
                line-height: 1.2;
            `;
            
            marker.appendChild(label);
            document.body.appendChild(marker);
            
            markers.push({
                id: idCounter,
                tagName: el.tagName.toLowerCase(),
                type: el.type || null,
                name: el.name || null,
                placeholder: el.placeholder || null,
                ariaLabel: el.getAttribute('aria-label') || null,
                innerText: el.innerText?.substring(0, 50) || null,
                rect: {
                    x: rect.left,
                    y: rect.top,
                    width: rect.width,
                    height: rect.height,
                    centerX: rect.left + rect.width / 2,
                    centerY: rect.top + rect.height / 2
                }
            });
            
            idCounter++;
        });
        
        return markers;
    }
    """
    
    # JavaScript to remove all markers
    MARKER_REMOVAL_SCRIPT = """
    () => {
        document.querySelectorAll('.vision-agent-marker').forEach(el => el.remove());
        document.querySelectorAll('[data-vision-agent-id]').forEach(el => {
            el.removeAttribute('data-vision-agent-id');
        });
    }
    """
    
    # JavaScript to get element by marker ID
    GET_ELEMENT_SCRIPT = """
    (id) => {
        const el = document.querySelector(`[data-vision-agent-id="${id}"]`);
        if (!el) return null;
        
        const rect = el.getBoundingClientRect();
        return {
            found: true,
            tagName: el.tagName.toLowerCase(),
            type: el.type || null,
            isVisible: rect.width > 0 && rect.height > 0,
            rect: {
                x: rect.left,
                y: rect.top,
                width: rect.width,
                height: rect.height,
                centerX: rect.left + rect.width / 2,
                centerY: rect.top + rect.height / 2
            }
        };
    }
    """
    
    def __init__(self, page: Page):
        """
        Initialize ElementMarker with a Playwright page.
        
        Args:
            page: Playwright Page object
        """
        self.page = page
        self.markers = []
    
    def inject_markers(self) -> list:
        """
        Inject numbered markers onto all interactive elements.
        
        Returns:
            List of marker metadata with element information
        """
        try:
            console.print("[dim]Injecting element markers...[/dim]")
            self.markers = self.page.evaluate(self.MARKER_INJECTION_SCRIPT)
            console.print(f"[green]✓ Marked {len(self.markers)} interactive elements[/green]")
            return self.markers
        except Exception as e:
            console.print(f"[red]✗ Failed to inject markers: {e}[/red]")
            return []
    
    def remove_markers(self):
        """Remove all injected markers from the page."""
        try:
            self.page.evaluate(self.MARKER_REMOVAL_SCRIPT)
            self.markers = []
            console.print("[dim]Removed element markers[/dim]")
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to remove markers: {e}[/yellow]")
    
    def get_element_info(self, element_id: int) -> dict:
        """
        Get information about a specific marked element.
        
        Args:
            element_id: The marker ID number
            
        Returns:
            Dictionary with element information or None if not found
        """
        try:
            return self.page.evaluate(self.GET_ELEMENT_SCRIPT, element_id)
        except Exception as e:
            console.print(f"[red]✗ Failed to get element info: {e}[/red]")
            return None
    
    def click_element(self, element_id: int) -> bool:
        """
        Click on an element by its marker ID.
        
        Args:
            element_id: The marker ID number
            
        Returns:
            True if click succeeded, False otherwise
        """
        info = self.get_element_info(element_id)
        if not info or not info.get('found'):
            console.print(f"[red]✗ Element #{element_id} not found[/red]")
            return False
        
        try:
            # Click at the center of the element
            center_x = info['rect']['centerX']
            center_y = info['rect']['centerY']
            self.page.mouse.click(center_x, center_y)
            console.print(f"[green]✓ Clicked element #{element_id} at ({center_x:.0f}, {center_y:.0f})[/green]")
            return True
        except Exception as e:
            console.print(f"[red]✗ Failed to click element #{element_id}: {e}[/red]")
            return False
    
    def fill_element(self, element_id: int, value: str) -> bool:
        """
        Fill a text input element by its marker ID.
        
        Args:
            element_id: The marker ID number
            value: Text to enter
            
        Returns:
            True if fill succeeded, False otherwise
        """
        info = self.get_element_info(element_id)
        if not info or not info.get('found'):
            console.print(f"[red]✗ Element #{element_id} not found[/red]")
            return False
        
        try:
            # Click to focus, then fill
            selector = f'[data-vision-agent-id="{element_id}"]'
            self.page.click(selector)
            self.page.fill(selector, value)
            console.print(f"[green]✓ Filled element #{element_id} with '{value[:30]}...'[/green]" if len(value) > 30 else f"[green]✓ Filled element #{element_id} with '{value}'[/green]")
            return True
        except Exception as e:
            console.print(f"[red]✗ Failed to fill element #{element_id}: {e}[/red]")
            return False
    
    def get_marker_summary(self) -> str:
        """
        Get a text summary of all marked elements.
        Useful for debugging.
        
        Returns:
            Formatted string describing all markers
        """
        if not self.markers:
            return "No markers present"
        
        lines = ["Marked Elements:"]
        for m in self.markers:
            desc = f"  #{m['id']}: <{m['tagName']}"
            if m.get('type'):
                desc += f" type='{m['type']}'"
            if m.get('placeholder'):
                desc += f" placeholder='{m['placeholder'][:20]}'"
            if m.get('innerText'):
                desc += f"> '{m['innerText'][:20]}'"
            else:
                desc += ">"
            lines.append(desc)
        
        return "\n".join(lines)
