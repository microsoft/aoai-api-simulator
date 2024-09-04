# Running and Deploying the Azure OpenAI API Simulator

- [Running and Deploying the Azure OpenAI API Simulator](#running-and-deploying-the-azure-openai-api-simulator)
  - [Getting Started](#getting-started)
  - [Running the Simulator Locally](#running-the-simulator-locally)
  - [Changing the Simulator Mode](#changing-the-simulator-mode)
  - [Running in Docker](#running-in-docker)
  - [Deploying to Azure Container Apps](#deploying-to-azure-container-apps)
  - [Using the Simulator with Restricted Network Access](#using-the-simulator-with-restricted-network-access)
    - [Unrestricted Network Access](#unrestricted-network-access)
    - [Semi-Restricted Network Access](#semi-restricted-network-access)
    - [Restricted Network Access](#restricted-network-access)
  - [Managing Large Recordings](#managing-large-recordings)


## Getting Started

The simplest way to work with and the simulator code is within a [Dev Container](https://code.visualstudio.com/docs/devcontainers/containers) in VS Code.

The repo contains Dev Container configuration that will sets up a container and install all of the dependencies needed to develop the simulator.

This repo is configured with a Visual Studio Code [dev container](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) that sets up a Python environment ready to work in, and will install the Pythong PyPI dependencies.

If you are not using a Dev Container then, after cloning the repo, you can install the Python dependencies using:

``` console
make install-requirements
```

## Running the Simulator Locally

Before running the Azure OpenAI API Simulator you should ensure that you have set up your local config. See [Azure OpenAI API Simulator Configuration Options](./docs/config.md) for details on how to do this.

To run the simulated API, use the following command from the repository root directory:

``` console
make run-simulated-api
```

## Changing the Simulator Mode

The `SIMULATOR_MODE` environment variable determines how the simulator behaves. You can either set this environment variable in the shell before running the simulator, or you can set it in the `.env` file.

For example, to use the API in record/replay mode:

```bash
# Run the API in record mode
SIMULATOR_MODE=record AZURE_OPENAI_ENDPOINT=https://mysvc.openai.azure.com/ AZURE_OPENAI_KEY=your-api-key make run-simulated-api

# Run the API in replay mode
SIMULATOR_MODE=replay make run-simulated-api
```

To run the API in generator mode, you can set the `SIMULATOR_MODE` environment variable to `generate` and run the API as above.

```bash
# Run the API in generator mode
SIMULATOR_MODE=generate make run-simulated-api
```

## Running in Docker

If you want to run the API simulator as a Docker container, there is a `Dockerfile` that can be used to build the image.

To build the image, run `docker build -t aoai-api-simulator .` from the `src/aoai-api-simulator` folder.

Once the image is built, you can run is using `docker run -p 8000:8000 -e SIMULATOR_MODE=record -e AZURE_OPENAI_ENDPOINT=https://mysvc.openai.azure.com/ -e AZURE_OPENAI_KEY=your-api-key aoai-api-simulator`.

Note that you can set any of the environment variable listed in the [Getting Started](#getting-started) section when running the container.
For example, if you have the recordings on your host (in `/some/path`) , you can mount that directory into the container using the `-v` flag: `docker run -p 8000:8000 -e SIMULATOR_MODE=replay -e RECORDING_DIR=/recording -v /some/path:/recording aoai-api-simulator`.

## Deploying to Azure Container Apps

The simulated API can be deployed to Azure Container Apps (ACA) to provide a publicly accessible endpoint for testing with the rest of your system:

Before deploying, set up a `.env` file. See the `sample.env` file for a starting point and add any configuration variables.
Once you have your `.env` file, run `make deploy-aca`. This will deploy a container registry, build and push the simulator image to it, and deploy an Azure Container App running the simulator with the settings from `.env`.

The ACA deployment also creates an Azure Storage account with a file share. This file share is mounted into the simulator container as `/mnt/simulator`.
If no value is specified for `RECORDING_DIR`, the simulator will use `/mnt/simulator/recording` as the recording directory.

The file share can also be used for setting the OpenAI deployment configuration or for any forwarder/generator config.


## Using the Simulator with Restricted Network Access

During initialization, TikToken attempts to download an OpenAI encoding file from a public blob storage account managed by OpenAI. When running the simulator in an environment with restricted network access, this can cause the simulator to fail to start.  
  
The simulator supports three networking scenarios with different levels of access to the public internet:  
  
- Unrestricted network access  
- Semi-restricted network access  
- Restricted network access  

Different build arguments can be used to build the simulator for each of these scenarios.

### Unrestricted Network Access  
  
In this mode, the simulator operates normally, with TikToken downloading the OpenAI encoding file from OpenAI's public blob storage account. This scenario assumes that the Docker container can access the public internet during runtime.
This is the default build mode.
  
### Semi-Restricted Network Access  
  
The semi-restricted network access scenario applies when the build machine has access to the public internet but the runtime environment does not. In this scenario,
 the simulator can be built using the Docker build argument `network_type=semi-restricted`. This will download the TikToken encoding file during the Docker image build process and cache it within the Docker image. The build process will also set the required `TIKTOKEN_CACHE_DIR` environment variable to point to the cached TikToken encoding file. 
  
### Restricted Network Access  

The restricted network access scenario applies when both the build machine and the runtime environment do not have access to the public internet. In this scenario, the simulator can be built using a pre-downloaded TikToken encoding file that must be included in a specific location. 

This can be done by running the [setup_tiktoken.py](./scripts/setup_tiktoken.py) script. 
Alternatively, you can download the [encoding file](https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken) from the public blob storage account and place it in the `src/aoai-api-simulator/tiktoken_cache` directory. Then rename the file to `9b5ad71b2ce5302211f9c61530b329a4922fc6a4`.

To build the simulator in this mode, set the Docker build argument `network_type=restricted`. The simulator and the build process will then use the cached TikToken encoding file instead of retrieving it through the public internet. The build process will also set the required `TIKTOKEN_CACHE_DIR` environment variable to point to the cached TikToken encoding file. 

## Managing Large Recordings

By default, the simulator saves the recording file after each new recorded request in `record` mode.
If you need to create a large recording, you may want to turn off the autosave feature to improve performance.

With autosave off, you can save the recording manually by sending a `POST` request to `/++/save-recordings` to save the recordings files once you have made all the requests you want to capture. You can do this using ` curl localhost:8000/++/save-recordings -X POST`. 
