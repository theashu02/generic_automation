"""
File Handler - Handles file uploads (resume, cover letter, etc.).
"""

import time
from pathlib import Path
from typing import Optional
from playwright.sync_api import Page
from .base import BaseHandler, scroll_element_into_view


class FileHandler(BaseHandler):
    """
    Handler for file upload elements.
    
    Supports:
    - Resume uploads
    - Cover letter uploads
    - Multiple file inputs on same page
    - Drag-and-drop zones (limited)
    """
    
    def __init__(
        self, 
        page: Page, 
        resume_path: Optional[Path] = None,
        cover_letter_path: Optional[Path] = None
    ):
        """
        Initialize file handler.
        
        Args:
            page: Playwright Page object
            resume_path: Path to resume file
            cover_letter_path: Path to cover letter file
        """
        super().__init__(page)
        self.resume_path = resume_path
        self.cover_letter_path = cover_letter_path
    
    def upload_resume(self, action: dict = None) -> bool:
        """
        Upload resume file.
        
        Args:
            action: Optional action dict (not used, for interface consistency)
            
        Returns:
            True if successful
        """
        if not self.resume_path or not self.resume_path.exists():
            self._log_warning(f"Resume file not found: {self.resume_path}")
            return False
        
        target_label = action.get('target_label', 'Resume') if action else 'Resume'
        
        # Try to find specific resume file input
        resume_locators = [
            self.page.locator('input[type="file"][name*="resume" i]'),
            self.page.locator('input[type="file"][id*="resume" i]'),
            self.page.locator('input[type="file"][accept*="pdf"]'),
            self.page.locator(f'label:has-text("{target_label}") input[type="file"]'),
            self.page.locator(f'label:has-text("{target_label}") ~ input[type="file"]'),
            # Generic - first file input (usually resume)
            self.page.locator('input[type="file"]').first,
        ]
        
        for locator in resume_locators:
            try:
                if locator.count() > 0:
                    locator.first.set_input_files(str(self.resume_path))
                    self._log_success("Uploaded resume", self.resume_path.name)
                    return True
            except Exception:
                continue
        
        self._log_warning("Could not find file input for resume")
        return False
    
    def upload_cover_letter(self, action: dict = None) -> bool:
        """
        Upload cover letter file.
        
        Args:
            action: Optional action dict
            
        Returns:
            True if successful
        """
        if not self.cover_letter_path or not self.cover_letter_path.exists():
            self._log_warning(f"Cover letter file not found: {self.cover_letter_path}")
            return False
        
        target_label = action.get('target_label', 'Cover Letter') if action else 'Cover Letter'
        
        # Look for file input near cover letter label/section
        file_inputs = self.page.locator('input[type="file"]')
        count = file_inputs.count()
        
        if count == 0:
            self._log_warning("No file input found for cover letter")
            return False
        
        try:
            # Try specific cover letter input
            cover_locators = [
                self.page.locator('input[type="file"][name*="cover" i]'),
                self.page.locator('input[type="file"][id*="cover" i]'),
                self.page.locator(f'label:has-text("{target_label}") input[type="file"]'),
                self.page.locator(f'label:has-text("{target_label}") ~ input[type="file"]'),
            ]
            
            for locator in cover_locators:
                try:
                    if locator.count() > 0:
                        locator.first.set_input_files(str(self.cover_letter_path))
                        self._log_success("Uploaded cover letter", self.cover_letter_path.name)
                        return True
                except Exception:
                    continue
            
            # If multiple file inputs, cover letter is usually second
            if count >= 2:
                file_inputs.nth(1).set_input_files(str(self.cover_letter_path))
                self._log_success("Uploaded cover letter", self.cover_letter_path.name, "second file input")
                return True
            
            # Last resort: use the only file input
            file_inputs.first.set_input_files(str(self.cover_letter_path))
            self._log_success("Uploaded cover letter", self.cover_letter_path.name)
            return True
            
        except Exception as e:
            self._log_warning(f"Failed to upload cover letter: {e}")
            return False
    
    def upload_file(self, action: dict) -> bool:
        """
        Generic file upload by label.
        
        Args:
            action: Action dict with target_label and optionally file_path
            
        Returns:
            True if successful
        """
        target_label = action.get('target_label', '')
        file_path = action.get('file_path', '')
        
        if not file_path:
            # Determine file based on label
            label_lower = target_label.lower()
            if 'resume' in label_lower or 'cv' in label_lower:
                return self.upload_resume(action)
            elif 'cover' in label_lower:
                return self.upload_cover_letter(action)
            else:
                self._log_warning(f"No file path specified for: {target_label}")
                return False
        
        file_path = Path(file_path)
        if not file_path.exists():
            self._log_warning(f"File not found: {file_path}")
            return False
        
        # Find file input by label
        locators = [
            self.page.locator(f'label:has-text("{target_label}") input[type="file"]'),
            self.page.locator(f'label:has-text("{target_label}") ~ input[type="file"]'),
            self.page.locator(f'[aria-label*="{target_label}" i] input[type="file"]'),
        ]
        
        for locator in locators:
            try:
                if locator.count() > 0:
                    locator.first.set_input_files(str(file_path))
                    self._log_success("Uploaded", file_path.name, target_label)
                    return True
            except Exception:
                continue
        
        self._log_warning(f"Could not find file input for: {target_label}")
        return False
