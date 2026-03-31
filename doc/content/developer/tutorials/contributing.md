# Contribution Process

To contribute changes to LAVA, follow this process:

1. [Create a GitLab account](#create-a-gitlab-account)
2. [Fork the code](#fork-the-code)
3. [Create a development branch](#create-a-development-branch)
4. [Make and commit your changes](#make-and-commit-your-changes)
5. [Push your changes](#push-your-changes)
6. [Submit a Merge Request](#submit-a-merge-request)
7. [Review and fix](#review-and-fix)
8. [Merging](#merging)

!!! note
    It is worth checking if someone already has a merge request which
    relates to your proposed changes. Check for open merge requests at
    <https://gitlab.com/lava/lava/merge_requests>

## Create a GitLab account

To be able to work with the LAVA Software Community Project, start by
creating an account on <https://gitlab.com/lava/>. Fill in details in
your profile, and make sure you add a public SSH key to your account.
You will need that to be able to push code changes.

## Fork the code

Fork the lava project in the GitLab web interface. This will set up a
copy of the lava project in your own personal namespace. From here, you
can create new branches as you like, ready for making changes.

## Create a development branch

Clone your fork of the lava software repository:

```shell
git clone git@gitlab.com:yourname/lava.git
```

We recommend always making a new local branch for your changes:

```shell
cd lava
git checkout -b <name-of-branch>
```

See also
[Create a branch](https://docs.gitlab.com/topics/git/branch/#create-a-branch).

## Make and commit your changes

Make and test the changes you need. The details here are down to you!

### Coding style

* Follow PEP8 style for Python code.
* Use one topic branch for each logical change.
* Include new unit tests in the proposed merge request.
* Write good commit messages — describe *what* you've changed, and *why*

See also
[How to Write a Git Commit Message](https://chris.beams.io/git-commit).

### Source code formatting

`black` and `isort` should be applied to **all** LAVA source code files.
Merge requests will **fail** CI if a change breaks the formatting.
`isort` should be run with `--profile black` option to ensure compatibility
with `black`.

When changing files formatted by `black`, make your changes and then run
`black` on all modified Python files before pushing the branch to GitLab.

### Signing off your commits

Use the `--signoff` or `-s` option to `git commit` to acknowledge that
you have the rights to submit this change under the terms of the
licenses applicable to the LAVA Software. This is commonly known as the
"Developer's Certificate of Origin" ([DCO](https://developercertificate.org/)),
and is used in a wide variety of other Open Source projects like the
Linux kernel.

```shell
git commit -s
```

GitLab supports including multiple commits in a single merge request, so
feel free to collect your changes in as many logical changesets as you
like. Don't include unrelated changes — use a separate branch (and
therefore a separate merge request) instead.

## Push your changes

Use `git push` to publish the changes on your branch back to your own
fork:

```shell
git push --set-upstream my_username my_branch
```

You can push here as many times as you like, as you make more changes.

Pushing to your fork will trigger the CI process — your changes will now
be automatically tested, and the results will be displayed for the MR.

## Submit a Merge Request

When your code is clean and ready to be reviewed, create a merge request
against the *master* branch of the original lava project. GitLab will
track all the changes that you have pushed to your development branch,
and present them together for review in one patchset.

There are some headlines that we expect in each merge request:

In the git commit message:

1. What does this change do?
2. Why was this change needed?
3. What are the relevant issue numbers?

In the merge request, as comments:

1. Are there points in the code the reviewer needs to double-check?
2. Screenshots or test job log files as links or attachments (if
   relevant)
3. Links to external resources like gold standard images to demonstrate
   how to use and/or test a new feature.

## Review and fix

If your MR failed its tests, you will receive a detailed email
explaining where the failures occurred. It is up to you to make any
fixes required.

If you are not sure how to fix things, please ask for help!

Fixes for test failures should be pushed to the same GitLab branch. Each
time you push, GitLab will automatically update your related merge
request and re-run the CI loop. As and when the code is functional,
maintainers will comment on your changes and if all is well they will
approve the merge. They may also ask you to make more changes — this is
an iterative process.

## Merging

As the final step in merging a change, we will want the list of commits
in the merge request to be squashed. The objective is to ensure that
each commit on the master branch is clean and intact, while also keeping
logical changes in separate commits.

* Ensure that commits to fix unit test failures, CI failures or other
  breakage are squashed into the parent commit.
* Ensure that separate logical changes remain as separate commits. It is
  often easier to use separate branches for this reason.
* Ensure that your commits are all rebased onto the current master
  branch.

Pushing the squashed branch will need you to use `git push --force` to
replace the existing commits in your merge request. The merge request
will get one final code review and if a Maintainer approves of the final
state, the change will be merged when the CI completes successfully.

!!! warning
    This is the **only** time that `git push --force` is ever
    recommended. Forcing a push makes it hard for other contributors to
    work on the changes by triggering lots of merge conflicts.

!!! info "See also"
    - [Contribution Guide](../methodology/contribute.md)
    - [Code of Conduct](../code-of-conduct.md)
