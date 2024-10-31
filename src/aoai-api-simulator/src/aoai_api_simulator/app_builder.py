import logging
import re
import traceback
from typing import Annotated

from aoai_api_simulator.auth import validate_api_key_header
from aoai_api_simulator.config_loader import get_config, set_config
from aoai_api_simulator.generator.manager import invoke_generators
from aoai_api_simulator.latency import LatencyGenerator
from aoai_api_simulator.limiters import apply_limits
from aoai_api_simulator.models import RequestContext
from aoai_api_simulator.record_replay.handler import RecordReplayHandler
from aoai_api_simulator.record_replay.persistence import YamlRecordingPersister
from fastapi import Depends, FastAPI, HTTPException, Request, Response

logger = logging.getLogger(__name__)

app = FastAPI()

repeated_quotes = re.compile(r"//+")

# pylint: disable-next=invalid-name
record_replay_handler = None


def apply_config():
    # pylint: disable-next=global-statement
    global record_replay_handler

    record_replay_handler = None

    logger.info("🚀 Starting aoai-api-simulator in %s mode", get_config().simulator_mode)
    logger.info("🗝️ Simulator api-key                       : %s", get_config().simulator_api_key)

    if get_config().simulator_mode in ["record", "replay"]:
        logger.info("📼 Recording directory                     : %s", get_config().recording.dir)
        logger.info("📼 Recording auto-save                     : %s", get_config().recording.autosave)
        persister = YamlRecordingPersister(get_config().recording.dir)

        record_replay_handler = RecordReplayHandler(
            simulator_mode=get_config().simulator_mode,
            persister=persister,
            forwarders=get_config().recording.forwarders,
            autosave=get_config().recording.autosave,
        )
    else:
        logger.info("📝 allow_undefined_openai_deployments      : %s", get_config().allow_undefined_openai_deployments)

    logger.info("📝 Using OpenAI deployments                : %s", get_config().openai_deployments)
    logger.info("📝 Using latencies                         : %s", get_config().latency)


def _default_validate_api_key_header(request: Request):
    validate_api_key_header(request=request, header_name="api-key", allowed_key_value=get_config().simulator_api_key)


# This middleware replaces double slashes in paths with a single slash
@app.middleware("http")
async def fix_double_slash_urls(request: Request, call_next):
    if repeated_quotes.search(request.url.path):
        new_url = request.url.replace(path=repeated_quotes.sub("/", request.url.path))
        request.scope["path"] = new_url.path

    response = await call_next(request)
    return response


@app.get("/")
async def root():
    return {"message": "👋 aoai-api-simulator is running"}


@app.post("/++/save-recordings")
def save_recordings(_: Annotated[bool, Depends(_default_validate_api_key_header)]):
    if get_config().simulator_mode == "record":
        logger.info("📼 Saving recordings...")
        record_replay_handler.save_recordings()
        logger.info("📼 Recordings saved")
        return Response(content="📼 Recordings saved", status_code=200)

    logger.warning("⚠️ Not saving recordings as not in record mode")
    return Response(content="⚠️ Not saving recordings as not in record mode", status_code=400)


@app.get("/++/config")
def config_get(_: Annotated[bool, Depends(_default_validate_api_key_header)]):
    # return a subset of the config as not all properties make sense (e.g. generator functions)
    config = get_config()
    return {
        "simulator_mode": config.simulator_mode,
        "latency": {
            "open_ai_embeddings": {
                "mean": config.latency.open_ai_embeddings.mean,
                "std_dev": config.latency.open_ai_embeddings.std_dev,
            },
            "open_ai_completions": {
                "mean": config.latency.open_ai_completions.mean,
                "std_dev": config.latency.open_ai_completions.std_dev,
            },
            "open_ai_chat_completions": {
                "mean": config.latency.open_ai_chat_completions.mean,
                "std_dev": config.latency.open_ai_chat_completions.std_dev,
            },
            "open_ai_translations": {
                "mean": config.latency.open_ai_translations.mean,
                "std_dev": config.latency.open_ai_translations.std_dev,
            },
        },
        "openai_deployments": (
            {
                name: {"tokens_per_minute": deployment.tokens_per_minute, "model": deployment.model}
                for name, deployment in config.openai_deployments.items()
            }
            if config.openai_deployments
            else None
        ),
    }


@app.patch("/++/config")
def config_patch(config: dict, _: Annotated[bool, Depends(_default_validate_api_key_header)]):
    original_config = get_config()

    # Config is a nested settings class to enable setting env var names on child items
    # As a result we need to update each level independently
    root_dict = {k: v for k, v in config.items() if k in ["simulator_mode", "allow_undefined_openai_deployments"]}
    new_config = original_config.model_copy(update=root_dict)
    if "latency" in config:
        if "open_ai_completions" in config["latency"]:
            new_config.latency.open_ai_completions = original_config.latency.open_ai_completions.model_copy(
                update=config["latency"]["open_ai_completions"]
            )
        if "open_ai_chat_completions" in config["latency"]:
            new_config.latency.open_ai_chat_completions = original_config.latency.open_ai_chat_completions.model_copy(
                update=config["latency"]["open_ai_chat_completions"]
            )
        if "open_ai_embeddings" in config["latency"]:
            new_config.latency.open_ai_embeddings = original_config.latency.open_ai_embeddings.model_copy(
                update=config["latency"]["open_ai_embeddings"]
            )
        if "open_ai_translations" in config["latency"]:
            new_config.latency.open_ai_translations = original_config.latency.open_ai_translations.model_copy(
                update=config["latency"]["open_ai_translations"]
            )

    # Update the config and re-initialize
    set_config(new_config)
    apply_config()

    return config_get(_)


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def catchall(request: Request):
    logger.debug("⚡ handling route: %s", request.url.path)

    response = None
    context = RequestContext(config=get_config(), request=request)

    try:
        # LatencyGenerator adds simulated latency to response
        # and emit associated metrics
        async with LatencyGenerator(context) as latency_generator:
            # Get response
            if get_config().simulator_mode == "generate":
                response = await invoke_generators(context, get_config().generators)
            elif get_config().simulator_mode in ["record", "replay"]:
                response = await record_replay_handler.handle_request(context)

            if not response:
                logger.error("No response found for request: %s", request.url.path)
                return Response(status_code=500)

            # Apply limits here so that that they apply to record/replay as well as generate
            if response.status_code < 300:
                response = await apply_limits(context, response)

            # pass the response to the latency generator
            # so that it can determine the latency to add
            latency_generator.set_response(response)

            return response
    except HTTPException as he:
        raise he
    # pylint: disable-next=broad-exception-caught
    except Exception as e:
        logger.error("Error: %s\n%s", e, traceback.format_exc())
        return Response(status_code=500)
