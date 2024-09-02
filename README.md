# Azure OpenAI API Simulator 

This repo is an exploration into creating a simulated API implementation for Azure OpenAI (AOAI). 

WARNING: This is a work in progress!

## Table of Contents

- [Azure OpenAI API Simulator](#azure-openai-api-simulator)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
    - [What is the Azure OpenAI API Simulator?](#what-is-the-azure-openai-api-simulator)
    - [Simulator Modes](#simulator-modes)
  - [When to use the Azure OpenAI API Simulator](#when-to-use-the-azure-openai-api-simulator)
  - [How to Get Started with the Azure OpenAI API Simulator](#how-to-get-started-with-the-azure-openai-api-simulator)
    - [Running and Deploying the Azure OpenAI API Simulator](#running-and-deploying-the-azure-openai-api-simulator)
    - [Configuring the Azure OpenAI API Simulator](#configuring-the-azure-openai-api-simulator)
    - [Extending the Azure OpenAI API Simulator](#extending-the-azure-openai-api-simulator)
    - [Contributing to the Azure OpenAI API Simulator](#contributing-to-the-azure-openai-api-simulator)
  - [Changelog](#changelog)
  - [Contributing](#contributing)
  - [Trademarks](#trademarks)

## Overview

### What is the Azure OpenAI API Simulator?

The Azure OpenAI API Simulator is a tool that allows you to easily deploy endpoints that simulate the OpenAI API.
A common use-case for the simulator is to test the behaviour your application under load, without making calls to the live OpenAI API endpoints. 

Let's illustrate this with an example...

Let's assume that you have built a chatbot that uses the OpenAI API to generate responses to user queries. Before your chatbot becomes popular, you want to ensure that it can handle a large number of users. One of the factors that will impact whether your chatbot can gracefully handle such load will be the way that your chatbot handles calls to OpenAI. However, when load testing your chatbot there are a number of reasons why you might not want to call the OpenAI API directly:

- **Cost**: The OpenAI API is a paid service, and running load tests against it can be expensive.
- **Consistency**: The OpenAI API is a live service, and the responses you get back can change over time. This can make it difficult to compare the results of load tests run at different times.
- **Rate Limits**: The OpenAI API has rate limits, and running load tests against it can cause you to hit these limits.
- **Latency**: The latency of OpenAI API calls might change over time, and this can impact the results of your load tests.

In fact, when considering Rate Limits and Latency, these might be things that you'd like to control. You may also want to inject latency, or inject rate limit issues, so that you can test how your chatbot deals with these issues.

**This is where the Azure OpenAI API Simulator plays its part!**

By using the Azure OpenAI API Simulator, instead of the live OpenAI API, you can reduce the cost of running load tests against the OpenAI API and ensure that your application behaves as expected under different conditions.

The `Azure OpenAI API Simulator presents the same interface as the live OpenAI API, allowing you to easily switch between the two, and then gives you full control over the responses that are returned.

### Simulator Modes

The Azure OpenAI API Simulator has two approaches to simulating API responses: 

1. **Generator Mode** - If you don't have any requirements around the content of the responses, the **Generator** approach is probably the easiest for you to use.
2. **Record/Replay Mode** - If you need to simulate specific responses, then the **Record/Replay** approach is likely the best fit for you.

#### Generator Mode

When run in Generator mode the Azure OpenAI API Simulator will create responses to requests on the fly. This mode is useful for load testing scenarios where it would be costly/impractical to record the full set of responses, or where the content of the response is not critical to the load testing.

![Simulator in generator mode](./docs/images/mode-generate.drawio.png "The Simulator in generate mode showing lorem ipsum generated content in the response")

#### Record/Replay Mode

With record/replay, the Azure OpenAI API Simulator is set up to act as a proxy between your application and Azure OpenAI. The Azure OpenAI API Simulator will then record requests that are sent to it along with the corresponding response from OpenAI API. 

![Simulator in record mode](./docs/images/mode-record.drawio.png "The Simulator in record mode proxying requests to Azure OpenAI and persisting the responses to disk")

Once a set of recordings have been made, the Azure OpenAI API Simulator can then be run in replay mode where it uses these saved responses without forwarding anything to the OpenAI API. 

Recordings are stored in YAML files which can be edited if you want to customise the responses.

![Simulator in replay mode](./docs/images/mode-replay.drawio.png "The Simulator in replay mode reading responses from disk and returning them to the client")

## When to use the Azure OpenAI API Simulator

The Azure OpenAI API Simulator has been used in the following scenarios:

- **Load Testing**: The Azure OpenAI API Simulator can be used to simulate the Azure OpenAI API in a development environment, allowing you to test how your application behaves under load. This can be useful both to save money when load testing or to allow you to test scaling the system beyond the Azure OpenAI capacity available in your development environment
- **Integration Testing**: The Azure OpenAI API Simulator can be used to run integration tests, for example in CI builds without needing to have credentials for an Azure OpenAI endpoint

The Azure OpenAI API Simulator is not a replacement for testing against the real Azure OpenAI API, but it can be a useful tool in your testing toolbox.

## How to Get Started with the Azure OpenAI API Simulator

### Running and Deploying the Azure OpenAI API Simulator
The document [Running and Deploying the Azure OpenAI API Simulator](./docs/running-deploying.md) includes instructions on running the Azure OpenAI API Simulator locally, packaging and deploying it in a Docker container, and also deploying the Azure OpenAI API Simulator to Azure Container Apps.

### Configuring the Azure OpenAI API Simulator
The behaviour of the Azure OpenAI API Simulator is controlled via a range of [Azure OpenAI API Simulator Configuration Options](./docs/config.md).

### Extending the Azure OpenAI API Simulator
There are also a number of [Azure OpenAI API Simulator Extension points](./docs/extensions.md) that allow you to customise the behaviour of the Azure OpenAI API Simulator. Extensions can be used to modify the request/response, add latency, or even generate responses.

### Contributing to the Azure OpenAI API Simulator

Finally, if you're looking to contribute to the Azure OpenAI API Simulator you should refer to the [Azure OpenAI API Simulator Development Guide](./docs/developing.md).

## Changelog

For a list of tagged versions and changes, see the [CHANGELOG.md](./CHANGELOG.md) file.

## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft 
trademarks or logos is subject to and must follow 
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
