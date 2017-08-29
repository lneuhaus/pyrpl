Workflow to submit code changes
*********************************

Preliminaries
=============

While our project PyRPL is yet too small to make it necessary to define
collaboration guidelines, we will just stick to the guidelines of the
`Collective Code Construction Contract
(C4) <https://rfc.zeromq.org/spec:22/C4/>`__. In addition, if you would
like to make a contribution to PyRPL, please do so by issuing a
pull-request that we will merge. Your pull-request should pass
unit-tests and be in PEP-8 style.

Use git to collaborate on code
==============================

As soon as you are able to, please use the git command line instead of
programs such as gitHub, since their functionality is less accurate than
the command line's.

1. Never work on the master branch. That way, you cannot compromise by
   mistake the functionality of the code that other people are using.

2. If you are developing a new function or the like, it is best to
   create your own branch. As soon as your development is fully
   functional and passes all unit tests, you can issue a pull request to
   master (or another branch if you prefer). Add a comment about the
   future of that branch, i.e. whether it can be deleted or whether you
   plan to work on the same branch to implement more changes. Even after
   the pull request has been merged into master, you may keep working on
   the branch.

3. It often occurs that two or more people end up working on the same
   branch. When you fetch the updates of other developers into your
   local (already altered) version of the branch with :code:`git pull` you
   will frequenctly encounter conflicts. These are mostly easy to
   resolve. However, they will lead to an ugly history. This situation,
   along with the standard issue, is well described `on
   stackoverflow <http://stackoverflow.com/questions/8509396/git-pull-results-in-extraneous-merge-branch-messages-in-commit-log>`__.
   There are two ways to deal with this:

   1. If you have only minor changes that can be summarized in one
      commit, you will be aware of this when you type::

          git fetch
          git status

      and you are shown that you are one or more commits
      behind the remote branch while only one or two local files are
      change. You should deal with this situation as follows::

          git stash
          git pull
          git stash pop

      This way, your local changes are saved onto the 'stash', then you
      update your local repository with the remote version that includes
      other developers' changes, and then you pop the stash onto that
      altered repository. The result is that only your own changes and the
      way you resolved the conflict will appear in the git history.

   2. If you have a considerable amount of changes, we can accept the
      ugly merge commits. Just stay with :code:`git pull` and put the
      keyword 'merge' into the commit message. To understand what is
      going on, read the copy-paste from the above link (copy-paste
      follows):

   For example, two people are working on the same branch. The branch
   starts as::

       ...->C1

   The first person finishes their work and pushes to the branch::

       ...->C1->C2

   The second person finishes their work and wants to push, but can't because they need to update.
   The local repository for the second person looks like::

       ...->C1->C3

   If the pull is set to merge, the second persons
   repository will look like::

       ...->C1->C3->M1
        \
          ->C2->

   It will appear in the merge commit that the second person has
   committed all the changes from C2. Nevertheless, C2 remains in the
   git history and is not completely lost. This way, the merge commit
   accuratly represents the history of the branch. It just somehow spams
   you with information, so you should always use the former option 3.i
   when you can.
