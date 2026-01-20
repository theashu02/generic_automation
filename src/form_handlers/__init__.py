"""
Form Handlers Package - Modular form interaction handlers for job applications.

This package provides generic handlers for different form element types:
- InputHandler: Text inputs and textareas
- CheckboxHandler: Checkbox interactions
- RadioHandler: Radio button selections
- DropdownHandler: Native and custom dropdowns
- FileHandler: File uploads (resume, cover letter)

All handlers are designed to work across multiple ATS platforms:
Greenhouse, Lever, Ashby, Workday, Keka, Weekday, etc.
"""

from .base import BaseHandler, scroll_element_into_view, wait_for_element
from .input_handler import InputHandler
from .checkbox_handler import CheckboxHandler
from .radio_handler import RadioHandler
from .dropdown_handler import DropdownHandler
from .file_handler import FileHandler
from .form_controller import FormController

__all__ = [
    "BaseHandler",
    "InputHandler", 
    "CheckboxHandler",
    "RadioHandler",
    "DropdownHandler",
    "FileHandler",
    "FormController",
    "scroll_element_into_view",
    "wait_for_element",
]
