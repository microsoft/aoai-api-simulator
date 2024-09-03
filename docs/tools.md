# Tools

## Test Clients

The Azure OpenAI API Simulator is designed to sit between an app that uses Azure OpenAI, and the Azure OpenAI API itself.

However, if you're helping to develop the simulator, testing its functionality, or you're just curious about how it works, you may not have an app that uses Azure OpenAI to test with. For this reason there are two test clients within this repo that you can use to test the simulator.

Folder | Description
--- | ---
`./tools/test-client` | A Python script that sends requests to an OpenAI API end point and displays the responses.
`./tools/test-client-web` | A web-based client that sends requests to an OpenAI API end point, and allows for more ad-hoc user interactions with that API.

Both of these test clients are bare-bones implementations of apps that use OpenAI, and are not intended to be used in production. They are intended to be used for testing and development purposes only.

