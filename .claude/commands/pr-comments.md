---
description: View PR comments with related code snippets
---

Arguments:
- `$1` (optional): branch name to checkout to, OR "all" to include resolved comments
- `$2` (optional): if `$1` is a branch name, use "all" here to include resolved comments

1. If `$1` is provided and is not "all", checkout to that branch first with `git checkout $1`
2. Check current branch with `git branch --show-current`
3. Find PR for current branch with `gh pr list --head <branch-name> --json number,url`
4. If no PR found:
   - Inform user: "No PR exists for this branch. Use /create-pr to create one."
   - Abort
5. Get PR review threads using GraphQL and filter to unresolved comments by default:
   ```
   gh api graphql -f query='
     query($owner: String!, $repo: String!, $pr: Int!) {
       repository(owner: $owner, name: $repo) {
         pullRequest(number: $pr) {
           reviewThreads(first: 100) {
             nodes {
               isResolved
               comments(first: 100) {
                 nodes { body author { login } path line diffHunk }
               }
             }
           }
         }
       }
     }
   ' -f owner={owner} -f repo={repo} -F pr={number} | jq '.data.repository.pullRequest.reviewThreads.nodes | map(select(.isResolved == false))'
   ```
   NOTE: If "all" argument is provided, omit the jq filter to show all comments (including resolved)
7. For each comment thread:
   - Show the file path and line number
   - Show the relevant code snippet (from `diffHunk`)
   - Show the comment body and author
   - Show resolved/unresolved status if showing all comments
   - If there are replies, show them nested under the parent comment
8. Format output clearly with separators between comments
