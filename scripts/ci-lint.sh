#!/bin/bash
set -e

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

if [[ -n "$GITHUB_BASE_REF" ]]; then
	# we have a base ref for a PR
	# check out that branch and silently run a lint check to save a baseline
	# then the linter will show the comparison against that baseline
	echo "Checking out base ref $GITHUB_BASE_REF to determine linter baseline..."
	git checkout "$GITHUB_BASE_REF"
	pylint "$script_dir/../src/aoai-api-simulator/"  --exit-zero > /dev/null

	git checkout -
fi

echo "Running linter..."
pylint "$script_dir/../src/aoai-api-simulator/"  --exit-zero
