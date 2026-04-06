---
description: Update PR title and description based on changes
---

1. Check current branch with `git branch --show-current`
2. Find PRs for current branch with `gh pr list --head <branch-name> --json number,title,url`
3. If no PRs found:
   - Inform user: "No PR exists for this branch. Use /create-pr to create one."
   - Abort
4. If multiple PRs found:
   - Ask user which PR to update (show PR numbers and titles)
5. Analyze the PR changes:
   - Get commits with `gh pr view <number> --json commits`
   - Get diff with `gh pr diff <number>`
6. Generate new title and description:
   - Title should be sentence case, derived from the actual changes
   - Body should summarize the actual changes made
7. Update PR with `gh api repos/<owner>/<repo>/pulls/<number> -X PATCH -f title="<title>" -f body="<body>"`
   - Use API directly to avoid `gh pr edit` deprecation errors with classic projects
