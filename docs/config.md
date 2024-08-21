# Configuring the simulator

- [Configuring the simulator](#configuring-the-simulator)
  - [Environment variables](#environment-variables)
  - [Latency](#latency)
  - [Rate Limiting](#rate-limiting)
  - [Large recordings](#large-recordings)
  - [Config API Endpoint](#config-api-endpoint)
  - [Open Telemetry](#open-telemetry)

There are a number of [environment variables](#environment-variables) that can be used to configure the simulator.
Additionally, some configuration can be changed while the simulator is running using the [config endpoint](#config-endpoint).

## Environment variables

When running the simulated API, there are a number of environment variables to configure:

| Variable                        | Description                                                                                                                                                                       |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SIMULATOR_MODE`                | The mode the simulator should run in. Current options are `record`, `replay`, and `generate`.                                                                                     |
| `SIMULATOR_API_KEY`             | The API key used by the simulator to authenticate requests. If not specified a key is auto-generated (see the logs). It is recommended to set a deterministic key value in `.env` |
| `RECORDING_DIR`                 | The directory to store the recorded requests and responses (defaults to `.recording`).                                                                                            |
| `OPENAI_DEPLOYMENT_CONFIG_PATH` | The path to a JSON file that contains the deployment configuration. See [OpenAI Rate-Limiting](#rate-limiting)                                                             |
| `ALLOW_UNDEFINED_OPENAI_DEPLOYMENTS`| If set to `True` (default), the simulator will generate OpenAI responses for any deployment. If set to `False`, the simulator will only generate responses for known deployments. |
| `AZURE_OPENAI_ENDPOINT`         | The endpoint for the Azure OpenAI service, e.g. `https://mysvc.openai.azure.com/`. Used when forwarding requests.                                                                 |
| `AZURE_OPENAI_KEY`              | The API key for the Azure OpenAI service. Used when forwarding requests                                                                                                           |
| `LOG_LEVEL`                     | The log level for the simulator. Defaults to `INFO`.                                                                                                                              |
| `LATENCY_OPENAI_*`              | The latency to add to the OpenAI service when using generated output. See [Latency](#latency) for more details.                                                                   |
| `RECORDING_AUTOSAVE`            | If set to `True` (default), the simulator will save the recording after each request (see [Large Recordings](#large-recordings)).                                                 |
| `EXTENSION_PATH`                | The path to a Python file that contains the extension configuration. This can be a single python file or a package folder - see [Extending the simulator](./extending.md)         |
| `AZURE_OPENAI_DEPLOYMENT`       | Used by the test app to set the name of the deployed model in your Azure OpenAI service. Use a gpt-35-turbo-instruct deployment.                                                  |

The examples below show passing environment variables to the API directly on the command line, but when running locally you can also set them via a `.env` file in the root directory for convenience (see the `sample.env` for a starting point).
The `.http` files for testing the endpoints also use the `.env` file to set the environment variables for calling the API.

> Note: when running the simulator it will auto-generate an API Key. This needs to be passed to the API when making requests. To avoid the API Key changing each time the simulator is run, set the `SIMULATOR_API_KEY` environment variable to a fixed value.

To run the simulated API, run `make run-simulated-api` from the repo root directory using the environment variables above to configure.

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

## Latency

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

## Rate Limiting

The simulator contains built-in rate limiting for OpenAI endpoints but this is still being refined.
The current implementation is a combination of token- and request-based rate-limiting.

To control the rate-limiting, set the `OPENAI_DEPLOYMENT_CONFIG_PATH` environment variable to the path to a JSON config file that defines the deployments and associated models and token limits. An example config file is shown below.

```json
{
    "deployment1" : {
        "model": "gpt-3.5-turbo",
        "tokensPerMinute" : 60000
    },
    "gpt-35-turbo-2k-token" : {
        "model": "gpt-3.5-turbo",
        "tokensPerMinute" : 2000
    },
    "gpt-35-turbo-1k-token" : {
        "model": "gpt-3.5-turbo",
        "tokensPerMinute" : 1000
    }
}
```

## Large recordings

By default, the simulator saves the recording file after each new recorded request in `record` mode.
If you need to create a large recording, you may want to turn off the autosave feature to improve performance.

With autosave off, you can save the recording manually by sending a `POST` request to `/++/save-recordings` to save the recordings files once you have made all the requests you want to capture. You can do this using ` curl localhost:8000/++/save-recordings -X POST`. 


## Config API Endpoint

The simulator exposes a `/++/config` endpoint that returns the current configuration of the simulator and allow the configuration to be updated dynamically.
This can be useful when you want to test how your application adapts to changing behaviour of the OpenAI endpoints.

A `GET` request to this endpoint will return a JSON object with the current configuration:

```json
{"simulator_mode":"generate","latency":{"open_ai_embeddings":{"mean":100.0,"std_dev":30.0},"open_ai_completions":{"mean":15.0,"std_dev":2.0},"open_ai_chat_completions":{"mean":19.0,"std_dev":6.0}},"openai_deployments":{"deployment1":{"tokens_per_minute":60000,"model":"gpt-3.5-turbo"},"gpt-35-turbo-1k-token":{"tokens_per_minute":1000,"model":"gpt-3.5-turbo"}}}
```

A `PATCH` request can be used to update the configuration
The body of the request should be a JSON object with the configuration values to update.

For example, the following request will update the mean latency for OpenAI embeddings to 1 second (1000ms):

```json
{"latency": {"open_ai_embeddings": {"mean": 1000}}}
```
## Open Telemetry

The simulator supports a set of basic Open Telemetry configuration options. These are:

| Variable| Description |
| ------- | ----------- |
| `OTEL_SERVICE_NAME`| Sets the value of the service name reported to Open Telemetry. Defaults to `aoai-api-simulator`|
| `OTEL_METRIC_EXPORT_INTERVAL`| The time interval (in milliseconds) between the start of two export attempts..|
