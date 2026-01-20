"""
Vision Agent - Automatic Job Application Filler
A multimodal AI agent that uses GPT-4o vision to fill job applications.
"""

from .vision_agent import VisionAgent
from .element_marker import ElementMarker

__version__ = "1.0.0"
__all__ = ["VisionAgent", "ElementMarker"]
