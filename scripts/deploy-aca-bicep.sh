#!/bin/bash
set -e

#
# Main script for coordinating of the simulator to Azure Container Apps (ACA)
#

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# Get the directory of the IaC scripts
scripts_iac_dir="$script_dir/../infra/bicep/scripts"

# Deploy base resources (e.g. container registry)
"$scripts_iac_dir/deploy-aca-base-bicep.sh"

# Build and push Docker image to container registry
"$script_dir/docker-build-and-push.sh"

# Deploy ACA etc
"$scripts_iac_dir/deploy-aca-infra-bicep.sh"

# est that the deployment is functioning
"$script_dir/deploy-aca-test.sh"

# show logs
"$script_dir/deploy-aca-show-logs.sh"

