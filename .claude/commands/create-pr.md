---
description: Create a PR from the current branch
---

1. Check current branch with `git branch --show-current`
2. If on `main` branch:
   - Create a new branch first following rules in @.claude/commands/create-branch.md
   - Derive branch name from the changes being made
   - Do NOT ask the user - create the branch yourself
3. Derive PR title from branch name:
   - Convert kebab-case to natural language
   - Capitalize only the first word (sentence case)
   - Example: Branch `fix-login-form` -> PR title `Fix login form`
4. Check what files have been changed with `git diff main --stat`
5. Create a concise PR description based on the changes:
   - Summarize what the PR does in one sentence
   - Add 2-4 bullet points highlighting key changes
   - Keep it brief - don't over-explain
6. Create PR with `gh pr create --title "<title>" --body "<body>" --base main`
7. If PR creation fails with authentication error:
   - Instruct user to run: `gh auth login`
