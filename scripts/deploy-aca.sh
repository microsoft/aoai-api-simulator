#!/bin/bash
set -e

#
# Main script for coordinating of the simulator to Azure Container Apps (ACA)
#

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

#Deploy base resources (e.g. container registry)
"$script_dir/deploy-aca-base.sh"

# Build and push Docker image to container registry
"$script_dir/docker-build-and-push.sh"

# Deploy ACA etc
"$script_dir/deploy-aca-infra.sh"

# Test that the deployment is functioning
"$script_dir/deploy-aca-test.sh"

# show logs
"$script_dir/deploy-aca-show-logs.sh"

