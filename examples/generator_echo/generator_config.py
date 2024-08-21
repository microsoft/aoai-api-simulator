# This file is an example of how you can define your generators
# Generators can be sync or async methods


from aoai_api_simulator.auth import validate_api_key_header
from aoai_api_simulator.models import Config, RequestContext
from fastapi import Response

def initialize(config: Config):
    """initialize is the entry point invoked by the simulator"""

    # Add the generator to the config if not already present
    # (NOTE: initialize may be called multiple times)
    if generate_echo_response not in config.generators:
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
