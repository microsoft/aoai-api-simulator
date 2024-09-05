# Tools

## Test Clients

The Azure OpenAI API Simulator is designed to sit between an app that uses Azure OpenAI, and the Azure OpenAI API itself.

However, if you're helping to develop the simulator, testing its functionality, or you're just curious about how it works, you may not have an app that uses Azure OpenAI API. 

For this reason there are a set of sample test clients within this repo that you can use to test the simulator, or simply use to call the Azure OpenAI API directly.

Folder | Description
--- | ---
`./tools/test-client` | A Python script that sends requests to an OpenAI API end point and displays the responses.
`./tools/test-client-web` | A web-based client that sends requests to an OpenAI API end point, and allows for more ad-hoc user interactions with that API.

Both of these test clients are bare-bones implementations of apps that use OpenAI, and are not intended to be used in production. They are sample code. They are intended to be used for testing and development purposes only. The following describes how these samples can be used.

### Test-Client

The `test-client` is a single Python script that will make called to an Azure OpenAI API endpoint, regardless of whether this is a similated API or the real API. To fully understand what this script does it it best to open the `./tools/test-client/app.py` file and read through the code. The following description provides a high-level overview of how to use this script.

You can run this script from the command line using the following `make` command:

``` console
make run-test-client
```

When you run this command it will launch the `test-client` script, and will use the configuration defined in your `.env` file.

#### Test-Client MODE

The Test-Client uses a `MODE` environment variable to determine exactly what sort of OpenAI API call it should make. The following table describes the various values you can specify:

`MODE` | Description
--- | ---
completion | Tests the completion API
chat | Test the chat completion API with a single chat turn
chatbot | Allows you to interact with the chat completion API using multiple chat turns
chatbot-stream | Allows you to interact the streaming chat completion API, using multiple chat turns
embedding | Tests the embedding API
doc-intelligence | Tests the document intelligence API

If you don't specify `MODE` then script will assume `completion`. 

You can set this `MODE` environment variable via the command line. 

``` console
MODE=chat make run-test-client
```

### Running the Test-Client against a local Azure OpenAI API Simulator

If you're running the Azure OpenAI API Simulator locally (either directly, or as a Docker container) there is a convinient `make` rule for this scenario:

``` console
MODE=chat make run-test-client-simulator-local
```

This will run the same Python script, but will set things up so that the test-client uses localhost endpoints (see `Makefile` for details).

### Running the Test-Client against an Azure Container Application Deployment

If you have already deployed the Azure OpenAI API Simulator to an Azure Container Application, you can run the test-client against that deployment using the following `make` command:

``` console
make run-test-client-simulator-aca
```

This will pick up the details of your deployment from the `./infra/output.json` file that this deployment will have created, and will then run the test client against the deployed simulator.

For more information on deploying the simulator, refer to the [Running and Deploying the Azure OpenAI API Simulator](./running-deploying.md) documentation.

### Test-Client-Web

The `test-client-web` folder contains a simple web app that will allow you to interact with either the Azure OpenAI API Simulator, or the real Azure OpenAI API.

To launch this web app, use the following `make` command:

``` console
make run-test-client-web
```
