"""
GPT-4o System Prompts for Vision Agent.
Centralized prompt templates for page analysis and action generation.
"""

# Main system prompt that instructs GPT-4o how to behave as a UI automation expert
SYSTEM_PROMPT = """You are an expert UI automation agent specialized in filling job applications.
You analyze screenshots of web pages and determine the next action to take.
You must output ONLY valid JSON - no markdown, no explanations outside the JSON structure.
Be precise and methodical. Only perform ONE action at a time."""


def get_analysis_prompt(user_data: dict, action_history: list = None) -> str:
    """
    Generate the analysis prompt for GPT-4o.
    
    Args:
        user_data: User's profile information
        action_history: List of previous actions taken (for context)
    
    Returns:
        Formatted prompt string
    """
    history_context = ""
    if action_history:
        recent_actions = action_history[-5:]  # Only last 5 actions for context
        history_context = f"\nRecent Actions Taken: {recent_actions}"
    
    return f"""
Analyze this job application page screenshot and determine the next action.

USER DATA:
{user_data}
{history_context}

TASK:
1. Identify the current page state (e.g., "Personal Info Form", "Work Experience", "Review Page", "Success/Confirmation")
2. Find the NEXT unfilled field or required action
3. Map it to the appropriate user data
4. Return a structured action command

RULES:
- Only perform ONE action at a time
- For text fields: provide the exact value to fill
- For dropdowns: identify the option to select (use "select" action)
- For radio button questions (e.g., "How did you hear about us?"): use "radio" action with value set to the option text (like "LinkedIn")
- For checkboxes: specify check/uncheck
- For resume file uploads: use "upload_resume" action
- For cover letter file uploads: use "upload_cover_letter" action (NOT fill)
- If the cover letter field says "Attach" or "Upload" it needs upload_cover_letter, not fill
- If you see "Submit" or "Apply" and all fields are filled: click it
- If you see a success/confirmation message: set status to "completed"
- If stuck in a loop or error state: set status to "error"

OUTPUT FORMAT (strict JSON):
{{
    "status": "processing" | "completed" | "error",
    "page_state": "description of current page",
    "reasoning": "brief explanation of what you see and why you chose this action",
    "action": {{
        "type": "fill" | "click" | "select" | "radio" | "check" | "upload_resume" | "upload_cover_letter" | "scroll_down" | "scroll_up" | "wait",
        "target_label": "visible text label or button text",
        "target_type": "input" | "button" | "select" | "checkbox" | "radio" | "file" | "link",
        "value": "text to enter, option to select, or radio option text (e.g., 'LinkedIn')",
        "confidence": 0.0 to 1.0
    }}
}}
"""


def get_som_analysis_prompt(user_data: dict, action_history: list = None) -> str:
    """
    Generate the Set-of-Mark analysis prompt.
    Used when elements are marked with numbered overlays.
    
    Args:
        user_data: User's profile information
        action_history: List of previous actions taken
    
    Returns:
        Formatted prompt string
    """
    history_context = ""
    if action_history:
        recent_actions = action_history[-5:]
        history_context = f"\nRecent Actions Taken: {recent_actions}"
    
    return f"""
Analyze this job application page screenshot. Interactive elements are marked with RED NUMBERED BOXES.

USER DATA:
{user_data}
{history_context}

TASK:
1. Identify the current page state
2. Find the numbered element that needs interaction next
3. Determine the action to perform on that element

RULES:
- Reference elements by their NUMBER ID (shown in red boxes)
- Only interact with ONE numbered element at a time
- If you need to type, specify the exact text
- For radio button questions: use "radio" action with the option text as value
- For cover letter file uploads: use "upload_cover_letter" action
- For unmarked areas that need scrolling, use scroll action

OUTPUT FORMAT (strict JSON):
{{
    "status": "processing" | "completed" | "error",
    "page_state": "description of current page",
    "reasoning": "brief explanation including which numbered element you're targeting",
    "action": {{
        "type": "fill" | "click" | "select" | "radio" | "check" | "upload_resume" | "upload_cover_letter" | "scroll_down" | "scroll_up" | "wait",
        "element_id": 5,
        "target_label": "what this element appears to be for",
        "value": "text to enter, option to select, or radio option text",
        "confidence": 0.0 to 1.0
    }}
}}
"""


def get_answer_generation_prompt(question: str, user_data: dict, resume_text: str = None) -> str:
    """
    Generate a prompt for answering open-ended application questions.
    
    Args:
        question: The question asked on the application
        user_data: User's profile information  
        resume_text: Optional parsed resume text for context
    
    Returns:
        Formatted prompt string
    """
    resume_context = f"\nRESUME CONTENT:\n{resume_text}" if resume_text else ""
    
    return f"""
Generate a professional response for this job application question.

QUESTION: {question}

USER BACKGROUND:
{user_data}
{resume_context}

REQUIREMENTS:
- Be concise but thorough (2-4 sentences unless more is clearly needed)
- Sound professional and enthusiastic
- Reference specific skills/experience from the user's background
- Avoid generic platitudes
- Do not make up any information not provided

OUTPUT: Just the answer text, no JSON wrapper.
"""


# Prompt for handling dropdown selections
SELECT_OPTIONS_PROMPT = """
Looking at this dropdown menu, identify the best matching option.

AVAILABLE OPTIONS (from screenshot):
[The AI should read these from the image]

USER WANTS TO SELECT: {target_value}

OUTPUT FORMAT (strict JSON):
{{
    "selected_option": "exact text of the option to click",
    "confidence": 0.0 to 1.0
}}
"""
