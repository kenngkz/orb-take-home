---
description: Commit and push changes with atomic commits
---

1. Check uncommitted changes with `git status`.
2. **If `y` flag is used:** ONLY commit files you modified in this session. Use `git add <specific-files>` for the files you worked on, not `git add .` or `git commit -a`. If you see files in `git status` that you didn't touch, exclude them.
3. Decide whether it should be one or more commits. Keep changes atomic - related changes that only work when applied together should be in the same commit. Present a SUCCINCT breakdown of what commits you're planning on creating to the user first. Ask user for confirmation UNLESS the user specifies otherwise by putting letter `y` right after the command, or says directly.
4. Commit current changes with one or more commits, each with relevant commit message and (optionally) description. Add a description only if it makes sense (don't include irrelevant details) and keep it succinct.
5. Once ALL COMMITS HAVE BEEN COMMITTED, push them.

Extra rules:

- **Efficiency:** Use the fewest commands necessary. Chain git commands with `&&` when appropriate (e.g., `git add file && git commit -m "msg" && git push`).
- Commit all types of modified/new files, including regular markdown files, config files, etc.
- With `y` flag: Only stage files you actually worked on. Trust `git status` output - if all files shown are yours, proceed. If there are extra files, use selective `git add`.
