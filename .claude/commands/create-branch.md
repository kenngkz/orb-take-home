---
description: Create a branch from a name or description
---

User provides either:

- A branch name directly, OR
- A description of the work (derive a kebab-case branch name from it)

## Branch Format

`<branch-name>` in kebab-case, descriptive of the work.

Example: `fix-login-form`, `add-document-search`, `refactor-streaming`

## Steps

1. Check current branch with `git branch --show-current`
2. If on `main`: Create branch directly (no prompt needed)
3. If NOT on `main`: Ask user: "Branch from main or current branch?"
4. Create branch using format above
5. Any staged/unstaged changes in the working directory will be brought onto the new branch automatically
