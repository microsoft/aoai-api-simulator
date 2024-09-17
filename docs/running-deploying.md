# Running and Deploying the Azure OpenAI API Simulator

- [Running and Deploying the Azure OpenAI API Simulator](#running-and-deploying-the-azure-openai-api-simulator)
  - [Getting Started](#getting-started)
  - [Running the Simulator Locally](#running-the-simulator-locally)
  - [Changing the Simulator Mode](#changing-the-simulator-mode)
  - [Deploying to Azure Container Apps](#deploying-to-azure-container-apps)
  - [Running in Docker](#running-in-docker)
    - [Example: Running Container in Record Mode](#example-running-container-in-record-mode)
    - [Example: Running Container in Replay Mode](#example-running-container-in-replay-mode)
  - [Using the Simulator with Restricted Network Access](#using-the-simulator-with-restricted-network-access)
    - [Unrestricted Network Access](#unrestricted-network-access)
    - [Semi-Restricted Network Access](#semi-restricted-network-access)
    - [Restricted Network Access](#restricted-network-access)
  - [Managing Large Recordings](#managing-large-recordings)

## Getting Started

The simplest way to work with the simulator code is from within a [Dev Container](https://code.visualstudio.com/docs/devcontainers/containers) in VS Code.

This repo contains Dev Container configuration that will set up a Dev Container and install all of the dependencies needed to develop the simulator, including the Python environment and dependencies.

Most of this documentation will assume that you are using a Dev Container, but it is possible to work outside of a Dev Container as well. If you are not using a Dev Container then, after cloning the repo, you can install the Python dependencies using:

```console
make install-requirements
```

## Running the Simulator Locally

1. Before running the Azure OpenAI API Simulator you should ensure that you have set up your local config. See [Azure OpenAI API Simulator Configuration Options](./config.md) for details on how to do this. 

The minimum set of environment variables you'll need in your `.env` file to run the simulator locally are as follows:

    ```dotenv
    SIMULATOR_API_KEY=my-test-key
    TEST_OPENAI_ENDPOINT=http://localhost:8000/
    TEST_OPENAI_KEY=my-test-key
    TEST_OPENAI_DEPLOYMENT=gpt-3.5-turbo-0613
    ```  

2. Start the simulator by running the following command in your terminal from the repository root directory:
  
    ```console
    make run-simulated-api
    ```
    Kill the process and run the command again to restart the simulator whenever you make changes to the config.
3. Now open the [test-aoai.http](test-aoai.http) file, and send the first POST request.  
4. You should receive an http `200` response with some generated completions. Check the terminal for any warnings or errors.  

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

## Deploying to Azure Container Apps

The simulated API can be deployed to Azure Container Apps (ACA) to provide a publicly accessible endpoint for testing with the rest of your system.

Before deploying, set up a `.env` file. See [Azure OpenAI API Simulator Configuration Options](./docs/config.md) for details on how to do this.

Once you have your `.env` file, you can deploy to Azure using the following command:

```console
make deploy-aca
```

This will deploy a container registry, build and push the simulator image to it, and deploy an Azure Container App running the simulator with the settings from `.env`.

The ACA deployment also creates an Azure Storage account with a file share. This file share is mounted into the simulator container as `/mnt/simulator`.

If no value is specified for `RECORDING_DIR`, the simulator will use `/mnt/simulator/recording` as the recording directory.

The file share can also be used for setting the OpenAI deployment configuration or for any forwarder/generator config.

## Running in Docker

If you want to run the API simulator as a Docker container, there is a `Dockerfile` that can be used to build the image.

To build the Docker image, run the following command from the repository root directory:

```console
make docker-build-simulated-api
```

Once the image is built, you can run this container using the following command:

```console
make docker-run-simulated-api
```

This make rule will pick up the .env file and pass the environment variables to the container. It will also mount a volume such that recordings from the simulator are written to a `.recording` folder off of the repository root. Review the `Makefile` for more details.

If you want to run the docker container with different environment variables, you can do so. Some examples of this are given below:

### Example: Running Container in Record Mode

```console
docker run -p 8000:8000 \
    -e SIMULATOR_MODE=record \
    -e AZURE_OPENAI_ENDPOINT=https://mysvc.openai.azure.com/ \
    -e AZURE_OPENAI_KEY=your-api-key aoai-api-simulator
```

### Example: Running Container in Replay Mode

This assumes you have some recordings in folder `/my_folder/my_recordings`.

```console
docker run -p 8000:8000 \
    -e SIMULATOR_MODE=replay \
    -e RECORDING_DIR=/recording \
    -v /my_folder/my_recordings:/recording \
    aoai-api-simulator
```

## Using the Simulator with Restricted Network Access

If you intend to run the Azure OpenAI API Simulator in an environment where there are restrictions to the public internet (e.g. behind a firewall) then this section of the docs explains how to build and configure the simulator to work in such an environment.

During initialization, the TikToken python package will attempt to download an OpenAI encoding file. It downloads thos file from a public blob storage account managed by OpenAI.

When running the simulator in an environment with restricted network access, this can cause the simulator to fail to start.

The simulator supports three networking scenarios with different levels of access to the public internet:

- Unrestricted network access (full access to public internet)
- Semi-restricted network access (build machine has public access, but runtime envinronment does not)
- Restricted network access (no access to public internet)

These modes are described in more detail below.

### Unrestricted Network Access

In this mode, the simulator operates normally, with TikToken downloading the OpenAI encoding file from OpenAI's public blob storage account.

This scenario assumes that the Docker container can access the public internet from the runtime environment. This is the default build mode.

### Semi-Restricted Network Access

The semi-restricted network access scenario applies when the build machine has access to the public internet but the runtime environment does not.

In this scenario, the simulator can be built using the Docker build argument `network_type=semi-restricted`.

This will download the TikToken encoding file during the Docker image build process and cache it within the Docker image.

The build process will also set the required `TIKTOKEN_CACHE_DIR` environment variable to point to the cached TikToken encoding file.

### Restricted Network Access

The restricted network access scenario applies when both the build machine and the runtime environment do not have access to the public internet.

In this scenario, the simulator can be built using a pre-downloaded TikToken encoding file that must be included in a specific location.

This can be done by running the [setup_tiktoken.py](./scripts/setup_tiktoken.py) script.

Alternatively, you can download the [encoding file](https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken) from the public blob storage account and place it in the `src/aoai-api-simulator/tiktoken_cache` directory. Then rename the file to `9b5ad71b2ce5302211f9c61530b329a4922fc6a4`.

To build the simulator in this mode, set the Docker build argument `network_type=restricted`.

The simulator and the build process will then use the cached TikToken encoding file instead of retrieving it through the public internet.

The build process will also set the required `TIKTOKEN_CACHE_DIR` environment variable to point to the cached TikToken encoding file.

## Managing Large Recordings

By default, the simulator saves the recording file after each new recorded request in `record` mode.

If you need to create a large recording, you may want to turn off the autosave feature to improve performance.

With autosave off, you can save the recording manually by sending a `POST` request to `/++/save-recordings` to save the recordings files once you have made all the requests you want to capture.

You can do this using the following command:

```console
curl localhost:8000/++/save-recordings -X POST
```
