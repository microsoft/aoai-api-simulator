# Configuring the Azure OpenAI API Simulator

- [Configuring the Azure OpenAI API Simulator](#configuring-the-azure-openai-api-simulator)
  - [Environment Variables](#environment-variables)
    - [Setting Environment Variables via the `.env` File](#setting-environment-variables-via-the-env-file)
  - [Configuring Endpoints](#configuring-endpoints)
  - [Configuring Latency](#configuring-latency)
  - [Configuring Rate Limiting](#configuring-rate-limiting)
  - [Open Telemetry Configuration](#open-telemetry-configuration)
  - [Config API Endpoint](#config-api-endpoint)

There are a number of [environment variables](#environment-variables) that can be used to configure the Azure OpenAI API Simulator.

Additionally, some configuration can be changed while the simulator is running using the [config endpoint](#config-api-endpoint).

## Environment Variables

When running the Azure OpenAI API Simulator, there are a number of environment variables to configure:

| Variable                        | Description |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SIMULATOR_MODE`                | The mode the simulator should run in. Current options are `record`, `replay`, and `generate`.                                                                                     |
| `SIMULATOR_API_KEY`             | The API key used by the simulator to authenticate requests. If not specified a key is auto-generated (see the logs). It is recommended to set a deterministic key value in `.env` |
| `RECORDING_DIR`                 | The directory to store the recorded requests and responses (defaults to `.recording`).                                                                                            |
| `OPENAI_DEPLOYMENT_CONFIG_PATH` | The path to a JSON file that contains the deployment configuration. See [OpenAI Rate-Limiting](#configuring-rate-limiting)                                                             |
| `ALLOW_UNDEFINED_OPENAI_DEPLOYMENTS`| If set to `True` (default), the simulator will generate OpenAI responses for any deployment. If set to `False`, the simulator will only generate responses for known deployments. |
| `AZURE_OPENAI_ENDPOINT`         | The endpoint for the Azure OpenAI service, e.g. `https://mysvc.openai.azure.com/`. Used by the simulator when forwarding requests.                                                                 |
| `AZURE_OPENAI_KEY`              | The API key for the Azure OpenAI service. Used by the simulator when forwarding requests                                                                                                           |
| `AZURE_OPENAI_DEPLOYMENT`       | The deployment name for your GPT model. Used by the simulator when forwarding requests.                                                  |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT`       | The deployment name for your embedding model. Used by the simulator when forwarding requests.                                                  |
| `AZURE_OPENAI_IMAGE_DEPLOYMENT`       | The deployment name for your image generation model. Used by the simulator when forwarding requests.                                                  |
| `LOG_LEVEL`                     | The log level for the simulator. Defaults to `INFO`.                                                                                                                              |
| `LATENCY_OPENAI_*`              | The latency to add to the OpenAI service when using generated output. See [Latency](#configuring-latency) for more details.                                                                   |
| `RECORDING_AUTOSAVE`            | If set to `True` (default), the simulator will save the recording after each request (see [Large Recordings](./running-deploying.md#managing-large-recordings)).                                                 |
| `EXTENSION_PATH`                | The path to a Python file that contains the extension configuration. This can be a single python file or a package folder - see [Extending the simulator](./extending.md)         |

There are also a set of environment variables that the test clients and tests will use. These are used to "point" the test clients at the a deployment of the simulator (local, or in Azure).

| Variable                        | Description |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TEST_OPENAI_ENDPOINT` | **Used by test client code only**. Defines the OpenAI-like endpoint that the test client will call. Most likely set to the location of your similator deployment.|
| `TEST_OPENAI_KEY` | **Used by test client code. only**. Defines the key that will be set to the `TEST_OPENAI_ENDPOINT` when making requests. Most likely set to the value of `SIMULATOR_API_KEY`.|
| `TEST_OPENAI_DEPLOYMENT` | **Used by test client code only**. Defines the GPT model deployment that the test client will request.|
| `TEST_OPENAI_EMBEDDING_DEPLOYMENT` | **Used by test client code only**. Defines the embedding model deployment that the test client will request.|
| `TEST_OPENAI_IMAGE_DEPLOYMENT`       | **Used by test client code only**. Defines the image generation model deployment that the test client will request.|

### Setting Environment Variables via the `.env` File

You can set the environment variables in the shell before running the simulator, or on the command line before running commands.

However, when running the Azure OpenAI API Simulator locally you may find it more convinient to set them via a `.env` file in the root directory.

The file `sample.env` lives in the root of this repository, and provides a starting point for the environment variables you may want to set. Copy this file, rename the copy to `.env`, and update the values as needed.

The `.http` files for testing the endpoints also use the `.env` file to set the environment variables for calling the API.

> Note: when running the simulator it will auto-generate an API Key. This needs to be passed to the API when making requests. To avoid the API Key changing each time the simulator is run, set the `SIMULATOR_API_KEY` environment variable to a fixed value.

## Configuring Endpoints

There are a number of environment variables that specify API endpoints. Each of these environment variables is named ending `_ENDPOINT`. For all such environment variables the format is `scheme://fqdn` or `scheme://fqdn:port`. e.g. `http://localhost:5000` or `https://example.openai.azure.com`. You should **not** include a trailing forward slash in the value of the environment variable.

## Configuring Latency

When running in `record` mode, the simulator captures the duration of the forwarded response.
This is stored in the recording file and used to add latency to requests in `replay` mode.

When running in `generate` mode, the simulator can add latency to the response based on the `LATENCY_OPENAI_*` environment variables.

| Variable Prefix                   | Description                                                                                                                                                                        |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `LATENCY_OPENAI_EMBEDDINGS`       | Speficy the latency to add to embeddings requests in milliseconds using `LATENCY_OPENAI_EMBEDDINGS_MEAN` and `LATENCY_OPENAI_EMBEDDINGS_STD_DEV`                                   |
| `LATENCY_OPENAI_COMPLETIONS`      | Specify the latency to add to completions _per completion token_ in milliseconds using `LATENCY_OPEN_AI_COMPLETIONS_MEAN` and `LATENCY_OPEN_AI_COMPLETIONS_STD_DEV`                |
| `LATENCY_OPENAI_CHAT_COMPLETIONS` | Specify the latency to add to chat completions _per completion token_ in milliseconds using `LATENCY_OPEN_AI_CHAT_COMPLETIONS_MEAN` and `LATENCY_OPEN_AI_CHAT_COMPLETIONS_STD_DEV` |

The default values are:

| Prefix                            | Mean | Std Dev |
| --------------------------------- | ---- | ------- |
| `LATENCY_OPENAI_EMBEDDINGS`       | 100  | 30      |
| `LATENCY_OPENAI_COMPLETIONS`      | 15   | 2       |
| `LATENCY_OPENAI_CHAT_COMPLETIONS` | 19   | 6       |

## Configuring Rate Limiting

The simulator contains built-in rate limiting for OpenAI endpoints but this is still being refined.

The current implementation is a combination of token- and request-based rate-limiting.

To control the rate-limiting, set the `OPENAI_DEPLOYMENT_CONFIG_PATH` environment variable to the path to a JSON config file that defines the deployments and associated models and token limits. An example config file is shown below.

```json
{
  "deployment1": {
    "model": "gpt-3.5-turbo",
    "tokensPerMinute": 60000
  },
  "gpt-35-turbo-2k-token": {
    "model": "gpt-3.5-turbo",
    "tokensPerMinute": 2000
  },
  "gpt-35-turbo-1k-token": {
    "model": "gpt-3.5-turbo",
    "tokensPerMinute": 1000
  }
}
```

## Open Telemetry Configuration

The simulator supports a set of basic Open Telemetry configuration options. These are:

| Variable                      | Description                                                                                     |
| ----------------------------- | ----------------------------------------------------------------------------------------------- |
| `OTEL_SERVICE_NAME`           | Sets the value of the service name reported to Open Telemetry. Defaults to `aoai-api-simulator` |
| `OTEL_METRIC_EXPORT_INTERVAL` | The time interval (in milliseconds) between the start of two export attempts..                  |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Sets up the app insights connection string for telemetry |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Sets up the OpenTelemetry OTLP exporter endpoint. This can be further customised using environment variables described [here](https://opentelemetry.io/docs/specs/otel/protocol/exporter/). i.e. `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`, `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT` or `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT`  |

## Config API Endpoint

The simulator exposes a `/++/config` endpoint that returns the current configuration of the simulator and allow the configuration to be updated dynamically.
This can be useful when you want to test how your application adapts to changing behaviour of the OpenAI endpoints.

A `GET` request to this endpoint will return a JSON object with the current configuration:

```json
{
  "simulator_mode": "generate",
  "latency": {
    "open_ai_embeddings": { "mean": 100.0, "std_dev": 30.0 },
    "open_ai_completions": { "mean": 15.0, "std_dev": 2.0 },
    "open_ai_chat_completions": { "mean": 19.0, "std_dev": 6.0 }
  },
  "openai_deployments": {
    "deployment1": { "tokens_per_minute": 60000, "model": "gpt-3.5-turbo" },
    "gpt-35-turbo-1k-token": {
      "tokens_per_minute": 1000,
      "model": "gpt-3.5-turbo"
    }
  }
}
```

A `PATCH` request can be used to update the configuration
The body of the request should be a JSON object with the configuration values to update.

For example, the following request will update the mean latency for OpenAI embeddings to 1 second (1000ms):

```json
{ "latency": { "open_ai_embeddings": { "mean": 1000 } } }
```
