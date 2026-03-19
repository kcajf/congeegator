---
name: make-pr
description: Make a pull request and get it in a passing state.
---

You've written some code / worked on a feature.

Now it's time to make a PR.

First, make sure this code is on its own, sensibly named branch. Use the feature/ and fix/ prefixes as appropriate.

Make sure that all changes from master/main are merged in.

If you previously made a PR in this session, it might have been merged. Check this. In which case, you'll need to make a new PR after having merged in main.

Make sure this branch & PR _only_ contain the changes from the thing we've just been working on - i.e. no crap from whatever was on your worktree.

Make the PR to github. Once the PR is up, watch it until CI passes. If CI fails, debug, and loop until it looks good.
Also check for merge conflicts, in case other code has been merged in the interim. In those cases, merge, push, and iterate until CI is green.


