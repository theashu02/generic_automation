"""
Configuration management for Vision Agent.
Loads settings from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()


class Config:
    """Central configuration class for Vision Agent."""
    
    # Paths
    BASE_DIR = Path(__file__).parent
    USER_DATA_DIR = BASE_DIR / "user_data"
    SCREENSHOTS_DIR = BASE_DIR / "screenshots"
    
    # OpenAI (strip whitespace to avoid header issues)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
    OPENAI_MODEL = "gpt-4o-mini"  # Cost-effective vision model
    
    # Browser settings
    HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
    
    # Automation limits
    MAX_STEPS = int(os.getenv("MAX_STEPS", "30"))
    ACTION_DELAY = float(os.getenv("ACTION_DELAY", "1.0"))
    
    # Image processing (lower resolution = lower token cost)
    SCREENSHOT_WIDTH = int(os.getenv("SCREENSHOT_WIDTH", "1024"))
    
    # Set-of-Mark
    ENABLE_SOM = os.getenv("ENABLE_SOM", "false").lower() == "true"
    
    @classmethod
    def validate(cls) -> bool:
        """Validate that required configuration is present."""
        errors = []
        
        if not cls.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY is required. Set it in .env file.")
        
        if errors:
            for error in errors:
                print(f"❌ Config Error: {error}")
            return False
        
        return True
    
    @classmethod
    def ensure_directories(cls):
        """Create required directories if they don't exist."""
        cls.USER_DATA_DIR.mkdir(exist_ok=True)
        cls.SCREENSHOTS_DIR.mkdir(exist_ok=True)
    
    @classmethod
    def get_default_user_data_path(cls) -> Path:
        """Get the default user.json path."""
        return cls.USER_DATA_DIR / "user.json"
    
    @classmethod
    def get_default_resume_path(cls) -> Path:
        """Get the default resume path."""
        return cls.USER_DATA_DIR / "resume.pdf"


if __name__ == "__main__":
    # Quick validation test
    Config.ensure_directories()
    if Config.validate():
        print("✅ Configuration is valid!")
    else:
        print("❌ Configuration has errors. Please check your .env file.")
