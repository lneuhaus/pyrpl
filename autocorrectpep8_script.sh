#!/bin/sh

if (( $AUTOCORRECTPEP8 > 0 )); then
  # Run pep8 on all .py files in all subfolders
  # We must ignore E402 module level import not at top of file
  # because of use case sys.path.append('..'); import <module>
  num_errors_before=`find . -name \*.py -exec pep8 --ignore=E402 {} + | wc -l`
  echo $num_errors_before
  
  cd "$TRAVIS_BUILD_DIR"
  git config --global user.email "leonhard.neuhaus@gmail.com"
  # From https://help.github.com/articles/setting-your-username-in-git/:
  # "Tip: You don't have to use your real name--any name works. Git 
  # actually associates commits by email address; the username is only 
  # used for identification. If you use your email address associated 
  # with a GitHub account, we'll use your GitHub username, instead of 
  # this name.
  git config --global user.name "Leos Auto-PEP8 Bot"
  git checkout $TRAVIS_BRANCH
  
  find . -name \*.py -exec autopep8 --recursive --aggressive --aggressive --in-place {} +
  num_errors_after=`find . -name \*.py -exec pep8 --ignore=E402 {} + | wc -l`
  echo $num_errors_after
  
  if (( $num_errors_after < $num_errors_before )); then
	  git commit -a -m "PEP-8 Fix"
	  git config --global push.default simple # Push only to the current branch.  
	  # Make sure to make the output quiet, or else the API token will 
	  # leak!  This works because the API key can replace your password.
	  git push --quiet
  fi
  cd "$TRAVIS_BUILD_DIR"
  
  # List the remaining errors - these will have to be fixed manually
  find . -name \*.py -exec pep8 --ignore=E402 {} +
fi
