# Working in this repo

## Platforms (always)

- **Every change applies to all three apps: iOS, web and Android**, unless that would be illogical
  (for example, an admin tool that only exists on web) or it has been discussed and agreed otherwise.
  If a change is done on fewer than three platforms, say which ones are missing and why, in the
  pull request and to the person you're working with.

## Branches and worktrees (always)

- **Every change happens in its own git worktree on its own branch**, never in the main checkout
  and never on `main`. Other people and sessions work here at the same time; a worktree keeps
  their changes and yours apart.
  `git worktree add ../<repo>-<branch> -b <branch> origin/main`
- **Use the branch and worktree you were told to use.** If you weren't told, ask which branch and
  worktree to use before changing anything. Don't pick one yourself.
- **Push a new branch as soon as you create it** (`git push -u origin <branch>`), before any work,
  so everyone can see it exists.

## Commit and push often (always)

- **Commit and push frequently**, after every small working step, not just at the end. Other
  branches and other devices may need to merge your work before it reaches `main`, so it has to be
  on GitHub, not only on your machine.
- **Don't rewrite commits you've already pushed** (no squashing or `--force` on pushed history):
  someone may have merged them, and rewriting breaks their merge. Write clear commit messages
  instead, saying what changed and why. Never rewrite `main` or someone else's branch.
- **Pull and merge `main` into your branch regularly** (`git fetch origin && git merge origin/main`),
  and before opening a pull request, so conflicts with other work show up early and small.
  Pull your own branch too (`git pull`): someone else may have pushed to it.
- Open a pull request into `main` when the work is ready; don't merge to `main` directly.
