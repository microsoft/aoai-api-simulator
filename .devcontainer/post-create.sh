#!/bin/bash
set -e

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# install requirements for convenience
make install-requirements

# Install the simulator code in the dev container so that types are 
# available for loaded extensions (forwarders/generators)
api_path=$(realpath "${script_dir}/../src/aoai-api-simulator" )

pip install "${api_path}"

