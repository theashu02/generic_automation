# 🤖 Vision Agent - Automatic Job Application Filler

A sophisticated multimodal AI agent that "sees" job application pages like a human and automatically fills them using GPT-4o vision capabilities and Playwright browser automation.

## 🌟 Features

- **Vision-First Approach**: Uses GPT-4o to analyze screenshots instead of brittle CSS selectors
- **Universal Compatibility**: Works with any job application platform (Lever, Greenhouse, Workday, etc.)
- **Set-of-Mark Mode**: Optional precise element targeting with numbered overlays
- **Smart Form Filling**: Automatically maps your profile data to form fields
- **Resume Upload**: Handles file upload fields automatically
- **Loop Detection**: Prevents getting stuck on the same field
- **Token Optimization**: Resizes screenshots to reduce API costs

## 📋 Prerequisites

- Python 3.10+
- OpenAI API key with GPT-4o access
- Chrome/Chromium browser

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure Environment

```bash
# Copy the example env file
copy .env.example .env

# Edit .env and add your OpenAI API key
# OPENAI_API_KEY=sk-your-key-here
```

### 3. Set Up Your Profile

Edit `user_data/user.json` with your information:

- Personal details (name, email, phone, address)
- Professional links (LinkedIn, GitHub, portfolio)
- Work history and education
- Skills and certifications
- Pre-written answers to common questions

Place your resume as `user_data/resume.pdf`

### 4. Run the Agent

```bash
# Basic usage
python main.py --url "https://jobs.lever.co/company/apply"

# With Set-of-Mark enabled (recommended for complex UIs)
python main.py --url "URL" --som

# Custom paths and settings
python main.py --url "URL" \
    --user-data "./my_profile.json" \
    --resume "./resume_2024.pdf" \
    --max-steps 50 \
    --delay 3.0
```

## 🎯 Command Line Options

| Option        | Short | Description                            |
| ------------- | ----- | -------------------------------------- |
| `--url`       | `-u`  | Job application URL (required)         |
| `--user-data` | `-d`  | Path to user.json                      |
| `--resume`    | `-r`  | Path to resume PDF                     |
| `--som`       | `-s`  | Enable Set-of-Mark mode                |
| `--headless`  | `-h`  | Run without visible browser            |
| `--max-steps` | `-m`  | Max automation steps (default: 30)     |
| `--delay`     |       | Seconds between actions (default: 1.0) |
| `--yes`       | `-y`  | Skip the start confirmation prompt     |

## 🔧 How It Works

### The Look-Think-Act Loop

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  1. LOOK   → Capture screenshot of current page             │
│     ↓                                                       │
│  2. THINK  → Send to GPT-4o: "What should I do next?"       │
│     ↓                                                       │
│  3. ACT    → Execute: fill field, click button, upload, etc │
│     ↓                                                       │
│  4. REPEAT → Go back to step 1 until done                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Set-of-Mark Mode

When enabled with `--som`, the agent:

1. Injects JavaScript to draw numbered red boxes on all interactive elements
2. Takes a screenshot showing these numbered elements
3. GPT-4o references elements by number: "Fill element #5 with email"
4. Agent clicks/fills using the element's coordinates

This provides **100% accurate targeting** even for icon-only buttons or complex UIs.

## 📁 Project Structure

```
generic_automation/
├── main.py                 # CLI entry point
├── config.py               # Configuration management
├── requirements.txt        # Python dependencies
├── .env                    # Your API keys (create from .env.example)
├── user_data/
│   ├── user.json           # Your profile information
│   ├── resume.pdf          # Your resume
│   └── README.md           # Setup instructions
├── src/
│   ├── vision_agent.py     # Main VisionAgent class
│   ├── element_marker.py   # Set-of-Mark JavaScript injection
│   ├── prompts.py          # GPT-4o prompt templates
│   └── utils.py            # Helper functions
└── screenshots/            # Captured screenshots (auto-created)
```

## ⚠️ Important Notes

### Rate Limiting

- Job sites may throttle or ban automated requests
- Use `--delay` to slow down actions (recommended: 2-5 seconds)
- Avoid running multiple applications in rapid succession

### CAPTCHA & Bot Detection

- Some sites have aggressive bot detection
- The agent uses anti-detection measures but may still be blocked
- Consider using the non-headless mode to handle CAPTCHAs manually

### Token Costs

- Each screenshot analysis costs OpenAI tokens
- Images are automatically resized to 1024px width to reduce costs
- Typical application: 10-20 API calls × ~1000 tokens each

### Ethical Use

- Only apply to jobs you're genuinely interested in
- Review the application before final submission
- Respect employers' time and hiring processes

## 🐛 Troubleshooting

### "OPENAI_API_KEY is required"

Make sure you created a `.env` file with your API key.

### "Element not found"

Try enabling Set-of-Mark mode: `python main.py --url "URL" --som`

### "Loop detected"

The agent may be stuck on the same field. Check:

- Is the field validation failing?
- Is data in user.json formatted correctly?
- Try increasing `--delay`

### "Rate limit exceeded"

Wait a few minutes and try again, or increase `--delay`.

## 📄 License

MIT License - Use responsibly!

## 🤝 Contributing

Contributions welcome! Areas for improvement:

- Additional platform-specific handlers
- CAPTCHA solving integration
- Multi-page application support
- Resume parsing for dynamic answer generation
