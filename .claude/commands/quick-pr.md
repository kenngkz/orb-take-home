---
description: Move current changes to a new branch and create a PR
---

Combines branch creation, committing, and PR creation into one flow.

## Steps

1. Check `git status` and `git diff` to understand current changes
2. If there are no changes (staged or unstaged), stop and tell the user
3. Derive a branch name from the changes (kebab-case, descriptive)
4. Create the branch from `main` using rules in @.claude/commands/create-branch.md
5. Commit the changes
6. Push the branch and create a PR following rules in @.claude/commands/create-pr.md
7. Switch back to `main` after the PR is created
