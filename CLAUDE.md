# Working in this repo

## Git workflow (always)

- **Work in a git worktree on its own branch**, never in the main checkout and never on `main`.
  Other people and sessions work here at the same time; a worktree keeps their changes and yours apart.
  `git worktree add ../<repo>-<branch> -b <branch> origin/main`
- **Push a new branch as soon as you create it** (`git push -u origin <branch>`), before any work,
  so everyone can see it exists.
- **Commit often** while you work: small commits are cheap and nothing gets lost.
- **When a subtask is done, squash its commits into one** clear commit (message says what the subtask
  did and why), then push. Rewriting your own unmerged branch is fine; use `git push --force-with-lease`.
  Never rewrite `main` or someone else's branch.
- **Push regularly** so others always have the latest work. Don't leave finished commits only on your machine.
- Open a pull request into `main` when the work is ready; don't merge to `main` directly.
