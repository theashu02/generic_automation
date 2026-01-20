"""
VisionAgent - The core automation agent.
Uses GPT-4o-mini vision to analyze web pages and Playwright to interact with them.
Implements the Look-Think-Act loop for intelligent form filling.
"""

import base64
import json
import time
from pathlib import Path
from typing import Optional
from PIL import Image
from openai import OpenAI
from playwright.sync_api import sync_playwright, Page, Browser
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .element_marker import ElementMarker
from .prompts import SYSTEM_PROMPT, get_analysis_prompt, get_som_analysis_prompt, get_answer_generation_prompt
from .utils import (
    format_user_data_for_prompt,
    print_action_summary,
    print_status_panel,
    extract_json_from_response,
    get_timestamp,
    cleanup_screenshots
)
from .token_tracker import TokenTracker
from .form_handlers import FormController

console = Console()


def scroll_element_into_view(page: Page, locator) -> bool:
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
            time.sleep(0.3)  # Brief wait after scroll
            return True
    except Exception:
        pass
    return False


class VisionAgent:
    """
    A multimodal AI agent that fills job applications using vision.
    
    The agent follows a Look-Think-Act loop:
    1. LOOK: Capture a screenshot of the current page
    2. THINK: Send screenshot to GPT-4o for analysis
    3. ACT: Execute the recommended action using Playwright
    4. Repeat until application is submitted or error occurs
    """
    
    def __init__(
        self,
        user_data_path: str | Path,
        resume_path: str | Path,
        api_key: str,
        headless: bool = False,
        max_steps: int = 30,
        action_delay: float = 2.0,
        screenshot_width: int = 1024,
        enable_som: bool = False,
        cover_letter_path: str | Path = None
    ):
        """
        Initialize the Vision Agent.
        
        Args:
            user_data_path: Path to user.json with profile information
            resume_path: Path to resume PDF file
            api_key: OpenAI API key
            headless: Run browser without visible window
            max_steps: Maximum automation steps (safety limit)
            action_delay: Seconds to wait between actions
            screenshot_width: Width to resize screenshots (reduces token cost)
            enable_som: Enable Set-of-Mark for precise element targeting
            cover_letter_path: Path to cover letter text file
        """
        self.user_data_path = Path(user_data_path)
        self.resume_path = Path(resume_path)
        self.cover_letter_path = Path(cover_letter_path) if cover_letter_path else None
        self.cover_letter_text = None
        self.api_key = api_key
        self.headless = headless
        self.max_steps = max_steps
        self.action_delay = action_delay
        self.screenshot_width = screenshot_width
        self.enable_som = enable_som
        
        # Load user data
        self._load_user_data()
        
        # Load cover letter if provided
        self._load_cover_letter()
        
        # Initialize OpenAI client
        self.client = OpenAI(api_key=api_key)
        
        # Initialize token tracker for cost monitoring
        self.token_tracker = TokenTracker(model="gpt-4o-mini")
        
        # Form controller (initialized when page is available)
        self.form_controller = None
        
        # Track action history to detect loops
        self.action_history = []
        
        # Screenshot directory
        self.screenshots_dir = Path(__file__).parent.parent / "screenshots"
        self.screenshots_dir.mkdir(exist_ok=True)
        
        console.print("[green]✓ Vision Agent initialized[/green]")
    
    def _load_user_data(self):
        """Load and format user data for prompts."""
        if not self.user_data_path.exists():
            raise FileNotFoundError(f"User data not found: {self.user_data_path}")
        
        with open(self.user_data_path, 'r', encoding='utf-8') as f:
            self.user_data = json.load(f)
        
        # Create condensed version for prompts (reduces tokens)
        self.user_data_prompt = format_user_data_for_prompt(self.user_data)
        
        console.print(f"[green]✓ Loaded user data from {self.user_data_path.name}[/green]")
    
    def _load_cover_letter(self):
        """Load cover letter from text file if provided."""
        if self.cover_letter_path and self.cover_letter_path.exists():
            with open(self.cover_letter_path, 'r', encoding='utf-8') as f:
                self.cover_letter_text = f.read().strip()
            
            # Add cover letter to user data for prompts
            self.user_data['cover_letter'] = self.cover_letter_text
            # Update the prompt version too
            self.user_data_prompt = format_user_data_for_prompt(self.user_data)
            
            console.print(f"[green]✓ Loaded cover letter from {self.cover_letter_path.name}[/green]")
        elif self.cover_letter_path:
            console.print(f"[yellow]⚠ Cover letter not found: {self.cover_letter_path}[/yellow]")
    
    def _dismiss_popups(self, page: Page):
        """
        Try to dismiss common cookie/privacy popups that block the form.
        """
        blockers = [
            "Accept", "Agree", "Accept All", "Allow all", "Continue", "Got it", "OK", "Close", "Dismiss"
        ]
        for label in blockers:
            locators = [
                page.get_by_role("button", name=label, exact=False),
                page.get_by_text(label, exact=False)
            ]
            for locator in locators:
                try:
                    if locator.count() > 0 and locator.first.is_visible():
                        locator.first.click(force=True)
                        time.sleep(0.2)
                        break
                except Exception:
                    continue
    
    def _prefill_obvious_fields(self, page: Page) -> int:
        """
        Deterministically fill common fields using user data to reduce GPT calls.
        
        Returns:
            Number of fields successfully prefilled
        """
        personal = self.user_data.get('personal_info', {})
        address = personal.get('address', {})
        links = self.user_data.get('professional_links', {})
        prefs = self.user_data.get('preferences', {})
        work_experience = self.user_data.get('work_experience', [])
        current_role = work_experience[0] if work_experience else {}
        
        actions = []
        
        def add_fill(labels, value):
            if not value:
                return
            label_list = [labels] if isinstance(labels, str) else labels
            actions.append((label_list, str(value)))
        
        add_fill(["First Name", "Given Name"], personal.get('first_name'))
        add_fill(["Last Name", "Family Name", "Surname"], personal.get('last_name'))
        add_fill(["Full Name", "Name"], personal.get('full_name') or f"{personal.get('first_name', '')} {personal.get('last_name', '')}".strip())
        add_fill(["Email", "Email Address"], personal.get('email'))
        add_fill(["Phone", "Phone Number", "Mobile"], personal.get('phone'))
        add_fill(["Street", "Street Address", "Address", "Address Line 1"], address.get('street'))
        add_fill(["City"], address.get('city'))
        add_fill(["State", "Province", "State/Province"], address.get('state'))
        add_fill(["ZIP", "Zip Code", "Postal Code", "Postcode"], address.get('zip_code'))
        add_fill(["Country"], address.get('country'))
        add_fill(["Location", "Current Location"], f"{address.get('city', '')}, {address.get('state', '')}".strip(", "))
        add_fill(["LinkedIn", "LinkedIn Profile"], links.get('linkedin'))
        add_fill(["GitHub", "Github"], links.get('github'))
        add_fill(["Portfolio", "Website", "Personal Website", "URL"], links.get('portfolio') or links.get('personal_website'))
        add_fill(["Current Company", "Current Employer", "Company"], current_role.get('company'))
        add_fill(["Current Title", "Job Title", "Role"], current_role.get('title'))
        add_fill(["Salary Expectation", "Expected Salary", "Compensation Expectation"], prefs.get('salary_expectation'))
        add_fill(["Notice Period", "Availability", "Available Start Date"], prefs.get('notice_period') or prefs.get('available_start_date'))
        if self.cover_letter_text:
            add_fill(["Cover Letter", "Cover letter text"], self.cover_letter_text)
        
        filled = 0
        for labels, value in actions:
            for label in labels:
                action = {
                    'type': 'fill',
                    'target_label': label,
                    'target_type': 'input',
                    'value': value,
                    'confidence': 0.95
                }
                if self.form_controller.execute(action):
                    filled += 1
                    self.action_history.append({
                        'step': 0,
                        'type': 'prefill',
                        'target': label,
                        'success': True
                    })
                    break
        if filled:
            console.print(f"[dim]Prefilled {filled} common fields without GPT[/dim]")
        return filled
    
    def _quick_file_uploads(self) -> int:
        """
        Try attaching resume/cover letter immediately to avoid extra GPT steps.
        
        Returns:
            Number of successful uploads
        """
        uploads = 0
        try:
            if self.resume_path and self.resume_path.exists():
                if self.form_controller.file_handler.upload_resume({'target_label': 'Resume'}):
                    uploads += 1
            if self.cover_letter_path and self.cover_letter_path.exists():
                if self.form_controller.file_handler.upload_cover_letter({'target_label': 'Cover Letter'}):
                    uploads += 1
        except Exception as e:
            console.print(f"[dim]Quick upload attempt skipped: {e}[/dim]")
        return uploads
    
    def _capture_screenshot(self, page: Page, filename: str = None) -> str:
        """
        Capture and optimize a screenshot of the current page.
        
        Args:
            page: Playwright page object
            filename: Optional custom filename
            
        Returns:
            Path to the saved screenshot
        """
        if filename is None:
            filename = f"step_{len(self.action_history) + 1}_{get_timestamp()}.jpg"
        
        screenshot_path = self.screenshots_dir / filename
        
        # Capture full page screenshot
        page.screenshot(path=str(screenshot_path), type="jpeg", quality=85)
        
        # Resize to reduce token cost
        self._resize_image(screenshot_path)
        
        return str(screenshot_path)
    
    def _resize_image(self, image_path: Path):
        """
        Resize image to target width while maintaining aspect ratio.
        This significantly reduces GPT-4o token cost.
        
        Args:
            image_path: Path to image file
        """
        with Image.open(image_path) as img:
            if img.width > self.screenshot_width:
                ratio = self.screenshot_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((self.screenshot_width, new_height), Image.Resampling.LANCZOS)
                img.save(image_path, "JPEG", quality=85)
    
    def _encode_image(self, image_path: str) -> str:
        """
        Encode an image file to base64 string.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Base64 encoded string
        """
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')
    
    def _analyze_page(self, screenshot_path: str, element_marker: Optional[ElementMarker] = None, step: int = 0) -> dict:
        """
        Send screenshot to GPT-4o-mini for analysis.
        
        Args:
            screenshot_path: Path to current screenshot
            element_marker: Optional ElementMarker if SOM is enabled
            step: Current step number for token tracking
            
        Returns:
            Parsed JSON response with action recommendation
        """
        base64_image = self._encode_image(screenshot_path)
        
        # Choose prompt based on whether Set-of-Mark is enabled
        if self.enable_som and element_marker and element_marker.markers:
            analysis_prompt = get_som_analysis_prompt(self.user_data_prompt, self.action_history)
        else:
            analysis_prompt = get_analysis_prompt(self.user_data_prompt, self.action_history)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Analyzing page with GPT-4o-mini...[/bold blue]"),
            console=console,
            transient=True
        ) as progress:
            progress.add_task("Analyzing", total=None)
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": analysis_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high"  # Use high detail for form analysis
                                }
                            }
                        ]
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=1000
            )
        
        # Record token usage
        self.token_tracker.record(response, step=step, action_type="analyze")
        
        response_text = response.choices[0].message.content
        result = extract_json_from_response(response_text)
        
        if not result:
            console.print(f"[red]✗ Failed to parse GPT response: {response_text}[/red]")
            return {"status": "error", "reasoning": "Failed to parse AI response"}
        
        return result
    
    def _execute_action(self, page: Page, command: dict, element_marker: Optional[ElementMarker] = None) -> bool:
        """
        Execute an action on the page based on GPT-4o-mini's recommendation.
        
        Args:
            page: Playwright page object
            command: Full command dict with action details
            element_marker: Optional ElementMarker for SOM-based targeting
            
        Returns:
            True if action succeeded, False otherwise
        """
        action = command.get('action', {})
        action_type = action.get('type', '')
        
        print_action_summary(action)
        
        try:
            # If using Set-of-Mark and we have an element_id, use coordinate-based interaction
            if self.enable_som and element_marker and action.get('element_id'):
                element_id = action['element_id']
                
                if action_type == 'fill':
                    success = element_marker.fill_element(element_id, action.get('value', ''))
                elif action_type in ('click', 'check', 'select'):
                    success = element_marker.click_element(element_id)
                else:
                    # Use FormController for other actions
                    success = self.form_controller.execute(action)
                
                return success
            
            # Use FormController for standard action execution
            return self.form_controller.execute(action)
            
        except Exception as e:
            console.print(f"[red]✗ Action failed: {e}[/red]")
            return False

    
    def _execute_standard_action(self, page: Page, action: dict) -> bool:
        """
        Execute action using standard Playwright locators.
        
        Args:
            page: Playwright page object
            action: Action dictionary
            
        Returns:
            True if successful
        """
        action_type = action.get('type', '')
        target_label = action.get('target_label', '')
        value = action.get('value', '')
        
        if action_type == 'fill':
            # Check if this is a cover letter field and we have cover letter text
            if 'cover' in target_label.lower() and 'letter' in target_label.lower():
                if self.cover_letter_text:
                    value = self.cover_letter_text
                    console.print("[dim]Using loaded cover letter text[/dim]")
            
            # Try multiple locator strategies (including textarea for cover letters)
            target_lower = target_label.lower().replace(" ", "")
            locators = [
                # Standard textbox role
                page.get_by_role("textbox", name=target_label),
                # By label
                page.get_by_label(target_label),
                # By placeholder
                page.get_by_placeholder(target_label),
                # Textarea elements (common for cover letters)
                page.locator(f'textarea[name*="{target_lower}"]'),
                page.locator(f'textarea[id*="{target_lower}"]'),
                page.locator(f'textarea[aria-label*="{target_label}"]'),
                # Any textarea near a label containing the text
                page.locator(f'label:has-text("{target_label}") + textarea'),
                page.locator(f'label:has-text("{target_label}") ~ textarea'),
                # Input elements
                page.locator(f'input[name*="{target_lower}"]'),
                page.locator(f'input[id*="{target_lower}"]'),
                # Generic textarea if looking for cover letter
                page.locator('textarea[name*="cover"]') if 'cover' in target_lower else None,
                page.locator('textarea#cover_letter') if 'cover' in target_lower else None,
                page.locator('textarea[data-field*="cover"]') if 'cover' in target_lower else None,
            ]
            
            # Filter out None entries
            locators = [loc for loc in locators if loc is not None]
            
            for locator in locators:
                try:
                    if locator.count() > 0:
                        # Scroll into view first
                        scroll_element_into_view(page, locator)
                        if locator.first.is_visible():
                            locator.first.fill(value)
                            console.print(f"[green]✓ Filled '{target_label}' with value[/green]")
                            return True
                except Exception:
                    continue
            
            # Scroll down and retry if elements weren't found
            console.print("[dim]Element not found, scrolling down to search...[/dim]")
            page.mouse.wheel(0, 400)
            time.sleep(0.5)
            
            for locator in locators:
                try:
                    if locator.count() > 0:
                        scroll_element_into_view(page, locator)
                        if locator.first.is_visible():
                            locator.first.fill(value)
                            console.print(f"[green]✓ Filled '{target_label}' after scroll[/green]")
                            return True
                except Exception:
                    continue
            
            # Last resort: try any visible textarea on the page
            if 'cover' in target_label.lower() or 'letter' in target_label.lower():
                try:
                    textareas = page.locator('textarea:visible')
                    if textareas.count() > 0:
                        textareas.first.fill(value)
                        console.print(f"[green]✓ Filled textarea with cover letter[/green]")
                        return True
                except Exception:
                    pass
            
            console.print(f"[yellow]⚠ Could not find input: {target_label}[/yellow]")
            return False
        
        elif action_type == 'click':
            locators = [
                page.get_by_role("button", name=target_label),
                page.get_by_role("link", name=target_label),
                page.get_by_text(target_label, exact=True),
                page.get_by_text(target_label),
                page.locator(f'[aria-label="{target_label}"]'),
                page.locator(f'button:has-text("{target_label}")'),
                page.locator(f'a:has-text("{target_label}")'),
            ]
            
            for locator in locators:
                try:
                    if locator.count() > 0:
                        # Scroll into view first
                        scroll_element_into_view(page, locator)
                        if locator.first.is_visible():
                            # Try force click for better reliability
                            locator.first.click(force=True)
                            console.print(f"[green]✓ Clicked '{target_label}'[/green]")
                            return True
                except Exception:
                    continue
            
            # Scroll down and retry
            page.mouse.wheel(0, 400)
            time.sleep(0.5)
            
            for locator in locators:
                try:
                    if locator.count() > 0:
                        scroll_element_into_view(page, locator)
                        if locator.first.is_visible():
                            locator.first.click(force=True)
                            console.print(f"[green]✓ Clicked '{target_label}' after scroll[/green]")
                            return True
                except Exception:
                    continue
            
            # JavaScript fallback
            try:
                js_result = page.evaluate(f'''
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
        
        elif action_type == 'select':
            # First, try native <select> elements
            native_select_locators = [
                page.locator(f'select[name*="{target_label.lower().replace(" ", "")}"]'),
                page.locator(f'select[id*="{target_label.lower().replace(" ", "")}"]'),
                page.get_by_label(target_label).locator('select'),
            ]
            
            for locator in native_select_locators:
                try:
                    if locator.count() > 0:
                        scroll_element_into_view(page, locator)
                        if locator.first.is_visible():
                            locator.first.select_option(label=value)
                            console.print(f"[green]✓ Selected '{value}' in native dropdown '{target_label}'[/green]")
                            return True
                except Exception:
                    continue
            
            # Handle custom dropdown components (click to open, then click option)
            console.print(f"[dim]Trying custom dropdown for '{target_label}'...[/dim]")
            
            # Step 1: Click on the dropdown trigger to open it
            dropdown_triggers = [
                page.get_by_role("combobox", name=target_label),
                page.get_by_label(target_label),
                page.locator(f'[aria-label*="{target_label}"]'),
                page.locator(f'[data-testid*="{target_label.lower().replace(" ", "")}"]'),
                # Common custom dropdown patterns
                page.locator(f'div:has-text("{target_label}") >> button'),
                page.locator(f'div:has-text("{target_label}") >> [role="button"]'),
                page.locator(f'label:has-text("{target_label}") + div'),
                page.locator(f'label:has-text("{target_label}") ~ div >> button'),
                page.locator(f'label:has-text("{target_label}") ~ div [role="combobox"]'),
                page.locator(f'label:has-text("{target_label}") ~ div'),
                # Clickable divs that might be dropdowns
                page.locator(f'[class*="select"]:has-text("{target_label}")'),
                page.locator(f'[class*="dropdown"]:has-text("{target_label}")'),
            ]
            
            dropdown_opened = False
            for trigger in dropdown_triggers:
                try:
                    if trigger.count() > 0:
                        scroll_element_into_view(page, trigger)
                        if trigger.first.is_visible():
                            trigger.first.click(force=True)
                            time.sleep(0.5)  # Wait for dropdown animation
                            dropdown_opened = True
                            console.print(f"[dim]Opened dropdown '{target_label}'[/dim]")
                            break
                except Exception:
                    continue
            
            if not dropdown_opened:
                # Try scrolling down first then retry
                page.mouse.wheel(0, 300)
                time.sleep(0.3)
                for trigger in dropdown_triggers:
                    try:
                        if trigger.count() > 0:
                            scroll_element_into_view(page, trigger)
                            if trigger.first.is_visible():
                                trigger.first.click(force=True)
                                time.sleep(0.5)
                                dropdown_opened = True
                                console.print(f"[dim]Opened dropdown '{target_label}' after scroll[/dim]")
                                break
                    except Exception:
                        continue
            
            if not dropdown_opened:
                console.print(f"[yellow]⚠ Could not open dropdown: {target_label}[/yellow]")
                # Still try to find and click the option directly
            
            # Step 2: Click on the option value
            time.sleep(0.3)  # Brief wait for options to render
            
            option_locators = [
                # Exact match first
                page.get_by_role("option", name=value),
                page.get_by_role("menuitem", name=value),
                page.get_by_role("listitem").filter(has_text=value),
                page.locator(f'[role="option"]:has-text("{value}")'),
                page.locator(f'[role="menuitem"]:has-text("{value}")'),
                page.locator(f'li:has-text("{value}")'),
                # Try with data attributes
                page.locator(f'[data-value="{value}"]'),
                page.locator(f'[data-value="{value.lower()}"]'),
                # Dropdown options in various formats
                page.locator(f'div[role="listbox"] >> text="{value}"'),
                page.locator(f'ul >> li:has-text("{value}")'),
                # Loose text match as last resort
                page.get_by_text(value, exact=True),
            ]
            
            for option in option_locators:
                try:
                    if option.count() > 0 and option.first.is_visible():
                        option.first.click(force=True)
                        time.sleep(0.2)
                        console.print(f"[green]✓ Selected '{value}' in custom dropdown '{target_label}'[/green]")
                        return True
                except Exception:
                    continue
            
            # Final fallback: try clicking anywhere that contains the value text
            try:
                visible_options = page.locator(f':visible:has-text("{value}")')
                if visible_options.count() > 0:
                    # Click the last visible one (often the dropdown option, not the label)
                    visible_options.last.click()
                    console.print(f"[green]✓ Clicked option containing '{value}'[/green]")
                    return True
            except Exception:
                pass
            
            console.print(f"[yellow]⚠ Could not select option '{value}' in '{target_label}'[/yellow]")
            return False
        
        elif action_type == 'check':
            # Handle checkbox selections
            target_lower = target_label.lower().replace(" ", "")
            
            checkbox_locators = [
                page.get_by_role("checkbox", name=target_label),
                page.get_by_label(target_label, exact=False),
                page.locator(f'input[type="checkbox"][name*="{target_lower}"]'),
                page.locator(f'input[type="checkbox"][id*="{target_lower}"]'),
                page.locator(f'label:has-text("{target_label}") input[type="checkbox"]'),
                page.locator(f'label:has-text("{target_label}")'),
                page.locator(f'[role="checkbox"]:has-text("{target_label}")'),
                page.locator(f'div:has-text("{target_label}") input[type="checkbox"]'),
            ]
            
            for locator in checkbox_locators:
                try:
                    if locator.count() > 0:
                        # Scroll into view first
                        scroll_element_into_view(page, locator)
                        if locator.first.is_visible():
                            element = locator.first
                            # Try force click first (works better with custom UIs)
                        try:
                            element.click(force=True)
                            time.sleep(0.2)
                            console.print(f"[green]✓ Checked '{target_label}' (force click)[/green]")
                            return True
                        except Exception:
                            pass
                        # Try regular check
                        try:
                            if not element.is_checked():
                                element.check(force=True)
                            console.print(f"[green]✓ Checked '{target_label}'[/green]")
                            return True
                        except Exception:
                            pass
                except Exception:
                    continue
            
            # JavaScript fallback for custom checkboxes
            try:
                js_result = page.evaluate(f'''
                    () => {{
                        const labels = document.querySelectorAll('label');
                        for (const label of labels) {{
                            if (label.textContent.toLowerCase().includes("{target_label.lower()}")) {{
                                const checkbox = label.querySelector('input[type="checkbox"]') || 
                                                label.previousElementSibling || 
                                                label.nextElementSibling ||
                                                document.getElementById(label.getAttribute('for'));
                                if (checkbox) {{
                                    checkbox.click();
                                    return true;
                                }}
                                label.click();
                                return true;
                            }}
                        }}
                        // Try clicking any element with the text
                        const el = document.evaluate('//*[contains(text(), "{target_label}")]', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                        if (el) {{
                            el.click();
                            return true;
                        }}
                        return false;
                    }}
                ''')
                if js_result:
                    console.print(f"[green]✓ Checked '{target_label}' (JS fallback)[/green]")
                    return True
            except Exception as e:
                console.print(f"[dim]JS checkbox fallback failed: {e}[/dim]")
            
            console.print(f"[yellow]⚠ Could not check: {target_label}[/yellow]")
            return False
        
        elif action_type == 'radio':
            # Handle radio button selections (like "How did you hear about us?")
            # The value contains the option text to select
            
            radio_locators = [
                # Try by radio role with the option name
                page.get_by_role("radio", name=value),
                # Try by label matching the value
                page.get_by_label(value, exact=True),
                page.get_by_label(value, exact=False),
                # Try radio input with value attribute
                page.locator(f'input[type="radio"][value="{value}"]'),
                page.locator(f'input[type="radio"][value="{value.lower()}"]'),
                page.locator(f'input[type="radio"][value*="{value.lower().replace(" ", "")}"]'),
                # Try by text near the radio button
                page.locator(f'label:has-text("{value}") input[type="radio"]'),
                page.locator(f'label:has-text("{value}")'),
                # Custom radio UIs
                page.locator(f'[role="radio"]:has-text("{value}")'),
                page.locator(f'div:has-text("{value}") >> input[type="radio"]'),
                page.locator(f'span:has-text("{value}")'),
            ]
            
            for locator in radio_locators:
                try:
                    if locator.count() > 0:
                        # Scroll into view first
                        scroll_element_into_view(page, locator)
                        if locator.first.is_visible():
                            element = locator.first
                            # Try force click (works better with custom UIs)
                            try:
                                element.click(force=True)
                                time.sleep(0.2)
                                console.print(f"[green]✓ Selected radio option '{value}' (force click)[/green]")
                                return True
                            except Exception:
                                pass
                            # Regular click
                            try:
                                element.click()
                                console.print(f"[green]✓ Selected radio option '{value}'[/green]")
                                return True
                            except Exception:
                                pass
                except Exception:
                    continue
            
            # Try clicking the text directly with force
            try:
                option_text = page.get_by_text(value, exact=True)
                if option_text.count() > 0:
                    option_text.first.click(force=True)
                    time.sleep(0.2)
                    console.print(f"[green]✓ Clicked radio option text '{value}'[/green]")
                    return True
            except Exception:
                pass
            
            # Try partial match with force click
            try:
                option_text = page.get_by_text(value, exact=False)
                if option_text.count() > 0:
                    for i in range(min(5, option_text.count())):
                        try:
                            if option_text.nth(i).is_visible():
                                option_text.nth(i).click(force=True)
                                time.sleep(0.2)
                                console.print(f"[green]✓ Clicked radio option '{value}'[/green]")
                                return True
                        except Exception:
                            continue
            except Exception:
                pass
            
            # JavaScript fallback for custom radio buttons
            try:
                js_result = page.evaluate(f'''
                    () => {{
                        // Find by label text
                        const labels = document.querySelectorAll('label, span, div');
                        for (const label of labels) {{
                            const text = label.textContent.trim().toLowerCase();
                            if (text === "{value.lower()}" || text.includes("{value.lower()}")) {{
                                // Try to find associated radio input
                                const radio = label.querySelector('input[type="radio"]') ||
                                             label.previousElementSibling ||
                                             label.parentElement.querySelector('input[type="radio"]');
                                if (radio && radio.type === 'radio') {{
                                    radio.click();
                                    return true;
                                }}
                                // Click the label itself
                                label.click();
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
                    console.print(f"[green]✓ Selected radio option '{value}' (JS fallback)[/green]")
                    return True
            except Exception as e:
                console.print(f"[dim]JS radio fallback failed: {e}[/dim]")
            
            console.print(f"[yellow]⚠ Could not find radio option: {value}[/yellow]")
            return False
        
        elif action_type == 'upload_resume':
            try:
                file_input = page.locator('input[type="file"]')
                if file_input.count() > 0:
                    file_input.first.set_input_files(str(self.resume_path))
                    console.print(f"[green]✓ Uploaded resume: {self.resume_path.name}[/green]")
                    return True
            except Exception as e:
                console.print(f"[red]✗ Failed to upload resume: {e}[/red]")
            return False
        
        elif action_type == 'upload_cover_letter':
            if not self.cover_letter_path or not self.cover_letter_path.exists():
                console.print("[yellow]⚠ Cover letter file not found[/yellow]")
                return False
            try:
                # Look for file input near cover letter label/section
                file_inputs = page.locator('input[type="file"]')
                count = file_inputs.count()
                
                if count == 0:
                    console.print("[yellow]⚠ No file input found for cover letter[/yellow]")
                    return False
                
                # If there are multiple file inputs, try to find the one for cover letter
                # Usually resume is first, cover letter is second
                if count >= 2:
                    file_inputs.nth(1).set_input_files(str(self.cover_letter_path))
                else:
                    # Try the first one if only one exists
                    file_inputs.first.set_input_files(str(self.cover_letter_path))
                
                console.print(f"[green]✓ Uploaded cover letter: {self.cover_letter_path.name}[/green]")
                return True
            except Exception as e:
                console.print(f"[red]✗ Failed to upload cover letter: {e}[/red]")
            return False
        
        elif action_type == 'scroll_down':
            page.mouse.wheel(0, 500)
            console.print("[green]✓ Scrolled down[/green]")
            return True
        
        elif action_type == 'scroll_up':
            page.mouse.wheel(0, -500)
            console.print("[green]✓ Scrolled up[/green]")
            return True
        
        elif action_type == 'wait':
            time.sleep(2)
            console.print("[green]✓ Waited[/green]")
            return True
        
        else:
            console.print(f"[yellow]⚠ Unknown action type: {action_type}[/yellow]")
            return False
    
    def _detect_loop(self) -> tuple[bool, str]:
        """
        Detect if the agent is stuck in a loop.
        
        Returns:
            Tuple of (is_looping, suggested_action)
        """
        if len(self.action_history) < 4:
            return False, ""
        
        # Check last 4 actions for same target
        recent = self.action_history[-4:]
        targets = [a.get('target', '') for a in recent]
        types = [a.get('type', '') for a in recent]
        successes = [a.get('success', True) for a in recent]
        
        # If same target keeps failing, it's a loop
        if len(set(targets)) == 1 and not all(successes):
            return True, "scroll_down"
        
        # If same action type repeating with failures
        if len(set(types)) == 1 and targets.count(targets[-1]) >= 3:
            return True, "scroll_down"
        
        # Check if we're stuck doing the same thing
        action_strs = [f"{a.get('type', '')}:{a.get('target', '')}" for a in recent]
        if len(set(action_strs)) == 1:
            return True, "scroll_down"
        
        # Too many consecutive failures
        if len(self.action_history) >= 5:
            last_5_success = [a.get('success', True) for a in self.action_history[-5:]]
            if not any(last_5_success):
                return True, "scroll_up"  # Try scrolling up if we've been failing
        
        return False, ""
    
    def run(self, url: str) -> bool:
        """
        Run the automation loop on a job application URL.
        
        Args:
            url: The job application URL to process
            
        Returns:
            True if application was submitted successfully
        """
        console.print(f"\n[bold blue]🚀 Starting Vision Agent[/bold blue]")
        console.print(f"[dim]URL: {url}[/dim]")
        console.print(f"[dim]Max Steps: {self.max_steps}[/dim]")
        console.print(f"[dim]Set-of-Mark: {'Enabled' if self.enable_som else 'Disabled'}[/dim]\n")
        
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled']  # Reduce bot detection
            )
            
            # Create browser context with realistic settings
            context = browser.new_context(
                viewport={'width': 1280, 'height': 900},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            page = context.new_page()
            
            # Initialize element marker if SOM is enabled
            element_marker = ElementMarker(page) if self.enable_som else None
            
            try:
                # Navigate to the job application
                console.print(f"[bold]Navigating to application...[/bold]")
                page.goto(url, wait_until='networkidle', timeout=30000)
                time.sleep(2)  # Wait for dynamic content
                
                # Close cookie/privacy popups that might hide the form
                self._dismiss_popups(page)
                
                # Initialize FormController for action execution
                self.form_controller = FormController(
                    page=page,
                    resume_path=self.resume_path,
                    cover_letter_path=self.cover_letter_path,
                    cover_letter_text=self.cover_letter_text
                )
                
                # Try deterministic autofill to reduce GPT calls
                prefilled = self._prefill_obvious_fields(page)
                uploads = self._quick_file_uploads()
                if prefilled or uploads:
                    console.print(f"[dim]Autofill kickstart: fields={prefilled}, uploads={uploads}[/dim]")
                time.sleep(0.5)
                
                step = 0
                while step < self.max_steps:
                    step += 1
                    console.print(f"\n[bold cyan]━━━ Step {step}/{self.max_steps} ━━━[/bold cyan]")
                    
                    # LOOK: Inject markers if SOM enabled, then capture screenshot
                    if self.enable_som and element_marker:
                        element_marker.inject_markers()
                    
                    screenshot_path = self._capture_screenshot(page)
                    console.print(f"[dim]Screenshot saved: {screenshot_path}[/dim]")
                    
                    # Remove markers before analysis if we want clean screenshots
                    # (keeping them for now as they help AI identify elements)
                    
                    # THINK: Analyze with GPT-4o-mini
                    decision = self._analyze_page(screenshot_path, element_marker, step=step)
                    
                    # Show status
                    print_status_panel(
                        decision.get('status', 'unknown'),
                        decision.get('page_state', 'Unknown'),
                        decision.get('reasoning', 'No reasoning provided')
                    )
                    
                    # Remove markers after screenshot if SOM enabled
                    if self.enable_som and element_marker:
                        element_marker.remove_markers()
                    
                    # Check for completion
                    if decision.get('status') == 'completed':
                        console.print("\n[bold green]✅ Application submitted successfully![/bold green]")
                        # Capture final screenshot as proof
                        self._capture_screenshot(page, "final_confirmation.jpg")
                        # Print token usage summary
                        self.token_tracker.print_summary()
                        return True
                    
                    # Check for error
                    if decision.get('status') == 'error':
                        console.print(f"\n[bold red]❌ Agent encountered an error: {decision.get('reasoning')}[/bold red]")
                        return False
                    
                    # ACT: Execute the recommended action
                    action = decision.get('action', {})
                    success = self._execute_action(page, decision, element_marker)
                    
                    # Track action for history
                    self.action_history.append({
                        'step': step,
                        'type': action.get('type'),
                        'target': action.get('target_label', action.get('element_id')),
                        'success': success
                    })
                    
                    # Detect loops and try to break out
                    is_looping, scroll_direction = self._detect_loop()
                    if is_looping:
                        console.print(f"\n[bold yellow]⚠ Loop detected! Trying to break out with {scroll_direction}...[/bold yellow]")
                        if scroll_direction == "scroll_up":
                            page.mouse.wheel(0, -500)
                        else:
                            page.mouse.wheel(0, 500)
                        time.sleep(0.5)
                        # Clear some history to prevent immediate re-detection
                        if len(self.action_history) > 5:
                            self.action_history = self.action_history[-3:]
                    
                    # Wait before next action
                    time.sleep(self.action_delay)
                
                console.print(f"\n[bold yellow]⚠ Reached maximum steps ({self.max_steps})[/bold yellow]")
                # Print token usage even on timeout
                self.token_tracker.print_summary()
                return False
                
            except Exception as e:
                console.print(f"\n[bold red]❌ Fatal error: {e}[/bold red]")
                import traceback
                traceback.print_exc()
                # Print token usage even on error
                self.token_tracker.print_summary()
                return False
            
            finally:
                # Cleanup
                cleanup_screenshots(self.screenshots_dir, keep_last=10)
                console.print("[dim]Closing browser...[/dim]")
                browser.close()
    
    def generate_answer(self, question: str) -> str:
        """
        Generate an answer for an open-ended application question.
        
        Args:
            question: The question to answer
            
        Returns:
            Generated answer text
        """
        prompt = get_answer_generation_prompt(question, self.user_data)
        
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",  # Use cheaper model for text generation
            messages=[
                {"role": "system", "content": "You are a professional job application assistant. Generate concise, relevant answers."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500
        )
        
        return response.choices[0].message.content.strip()
