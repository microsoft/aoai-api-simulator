# Extending the simulator

- [Extending the simulator](#extending-the-simulator)
  - [Running with an extension](#running-with-an-extension)
  - [Creating a custom forwarder extension](#creating-a-custom-forwarder-extension)
    - [Creating a custom generator extension](#creating-a-custom-generator-extension)
  - [Document Intelligence extensions](#document-intelligence-extensions)
    - [Document Intelligence forwarder](#document-intelligence-forwarder)
    - [Document Intelligence generator](#document-intelligence-generator)
  - [Customising rate limiting](#customising-rate-limiting)


The simulator allows extending some aspects of the behavior without modifying the original source code.

An extension can be either a single python file or a package folder.
The extension should contain an `initialize` method that receives the simulator configuration and can modify it.

The `initialize` method in an extension is psased the simulator configuration object.
Through this an extension can add/remove forwarders, generators, and limiters, as well as modifying other aspects of the configuration.

NOTE: the `initialize` method may be called multiple times, so ensure that any configuration changes are idempotent.

## Running with an extension

To run with an extension,  set the `EXTENSION_PATH` environment variable:

```bash
SIMULATOR_MODE=record EXTENSION_PATH=/path/to/extension.py make run-simulated-api
```

Or via Docker:

```bash
docker run -p 8000:8000 -e SIMULATOR_MODE=record -e EXTENSION_PATH=/mnt/extension.py -v /path/to/extension.py:/mnt/extension.py
```

## Creating a custom forwarder extension

When running in `record` mode, the simulator forwards requests on to a backend API and records the request/response information for later replay.

The default implementation uses the `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_KEY` environment variables to forward requests on to Azure OpenAI.

To forward requests on to a different backend API, you can create a custom forwarder extension.

An extension needs to have an `initialize` method as shown below:

```python
from typing import Callable
from fastapi import Request
import requests

from aoai_api_simulator.auth import validate_api_key_header
from aoai_api_simulator.models import Config, RequestContext

async def forward_to_my_host(context: RequestContext) -> Response | None:
    # Determine whether the request matches your forwarder
    request = context.request
    if not request.url.path.startswith("/your-base-path/"):
        # not for us!
        return None

    # This is an example of how you can use the validate_api_key_header function
    # This validates the "ocp-apim-subscription-key" header in the request against the configured API key
    validate_api_key_header(
        request=request, header_name="x-api-key", allowed_key_value=context.config.simulator_api_key
    )

    # build up the forwarded request from the incoming request
    # you may need to modify the headers or other properties
    url = "<build up target url>"
    body = await request.body()
    response = requests.request(
        request.method,
        url,
        headers=request.headers,
        data=body,
    )
    return response

def initialize(config: Config):
    # initialize is the entry point invoked by the simulator
    # here we append the custom forwarder to the list of forwarders
    config.recording.forwarders.append(forward_to_my_host)
```

The `initialize` method receives the simulator config and can manipulate it to change the simulator behavior.

The `config.recording.forwarders` property is a list of functions that are called in order to forward requests on to the backend API.
Each function can by sync or async and can return a number of options:

- A `Response` object from the `fastapi` package
- A `Response` object from the `requests` package
- A `dict` object (see below for details)
- `None`

If a forwarding function returns a `Response` object then that response is used as the response for the request and is added to the recording.

If a forwarding function returns a `dict` object, it should contain a `response` property and a `persist` property.
The `response` can be from either `fastapi` or `requests`. The `persist` value is a boolean indicating whether the request/response should be persisted.
This can be useful if you are forwarding to an API that uses the [async pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/async-request-reply) as you can skip recording the intermediate responses while polling for completion and only save the final response with the completed value.

If a forwarding function returns `None` then the next forwarding function is called.
This can be useful if you need to be able to forward to multiple back-end APIs you can include logic in each forwarding function to determine whether it should take actions.

```python
async def forward_to_my_host(request: Request) -> Response | None:
    if not request.url.path.startswith("/my-api/"):
        # assume not a request this forwarder can handle
        # return None to allow another forwarder to try
        return None

    # This is an example of how you can use the validate_api_key_header function
    # This validates the "api-key" header in the request against the configured API key
    validate_api_key_header(request=request, header_name="api-key", allowed_key_value=context.config.simulator_api_key)

    # rest of the implementation here...
```

### Creating a custom generator extension

If you want to add custom logic to generate responses in `generate` mode, you can create a custom generator extension.
This allows you to replace the default lorem ipsum responses with responses that are more relevant to your scenario, or are based on the input request.

An extension needs to have an `initialize` method as shown below:

```python
from aoai_api_simulator.models import Config, RequestContext
from fastapi import Response

def initialize(config: Config):
    # initialize is the entry point invoked by the simulator
    # here we append the custom generator to the list of generators
    config.generators.append(generate_echo_response)

async def generate_echo_response(context: RequestContext) -> Response | None:
    request = context.request
    if request.url.path != "/echo" or request.method != "POST":
        return None

    # This is an example of how you can use the validate_api_key_header function
    # This validates the "api-key" header in the request against the configured API key
    validate_api_key_header(request=request, header_name="api-key", allowed_key_value=context.config.simulator_api_key)

    request_body = await request.body()
    return Response(content=f"Echo: {request_body.decode("utf-8")}", status_code=200)
```

If the generator function returns a `Response` object then that response is used as the response for the request.
If the generator function returns `None` then the next generator function is called.

## Document Intelligence extensions

The repo includes a couple of example extensions for Document Intelligence that are intended to server as  starter implmementations.

### Document Intelligence forwarder

The document intelligence forwarder extension is in the `examples/forwarder_doc_intelligence` folder.
This extension allows you to forward requests to the Document Intelligence service and record the responses for later replay. 

### Document Intelligence generator

The document intelligence generator extension is in the `examples/generator_doc_intelligence` folder.
The extension includes a generator and custom rate-limiter.

The generator will return the right shape of response using lorem ipsum text.
You will likely want to make some tweaks to the example generator depending on the model that you use in your application and the aspects of the response that you use in your application.

Rate-limiting for Document Intelligence endpoints is a standard requests per second (RPS) limit.
The default limit for the simulator is 15 RPS based on the default for an S0 tier service (see https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/service-limits?view=doc-intel-4.0.0).

This rate-limit only applies to the request submission endpoint and not to the results endpoint.

To control the rate-limiting, set the `DOC_INTELLIGENCE_RPS` environment variable to the desired RPS limit (set to a negative number to disable rate-limiting).

## Customising rate limiting

The rate limiting behaviour can be customised by extensions.
This can be useful if you want to implement different rate limiting behaviour or if you want to add rate limiting to a custom forwarder/generator.

An example of a custom generator can be found in the `examples/generator_doc_intelligence` folder.

The simulator configuration stores a dictionary of rate limiters.
The `RequestContext` associated with a request contains a `values` dictionary used to store information about the request.
The value of the `Limiter` key in the `RequestContext.values` dictionary is used to look up the rate limiter in the rate limiters dictionary.

