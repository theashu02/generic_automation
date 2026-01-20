# User Data Setup

This folder contains your personal information for automated job applications.

## Files Required

### 1. `user.json` (Required)

Your profile information that the agent uses to fill applications.

**How to set up:**

1. Open `user.json` in a text editor
2. Replace all placeholder values with your actual information
3. Leave fields blank (`""`) if they don't apply to you

**Important sections:**

- `personal_info` - Your name, email, phone, address
- `professional_links` - LinkedIn, GitHub, portfolio URLs
- `work_authorization` - Visa/work permit status
- `education` - Your educational background
- `work_experience` - Your job history
- `skills` - Technical and soft skills
- `common_questions` - Pre-written answers to common application questions

### 2. `resume.pdf` (Required)

Your resume in PDF format.

**How to set up:**

1. Save your resume as `resume.pdf` in this folder
2. Make sure it's a clean, ATS-friendly format

## Tips

1. **Be Complete**: The more information you provide, the better the agent can fill applications
2. **Be Accurate**: Double-check all information for typos
3. **Update Regularly**: Keep your `user.json` and resume current
4. **Multiple Versions**: Create different `user_XX.json` files for different job types

## Privacy Note

⚠️ This folder contains sensitive personal information.

- Never commit this folder to a public repository
- The `.gitignore` file should exclude `user.json` and `resume.pdf`
