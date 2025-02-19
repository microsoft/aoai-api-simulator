import importlib
import json
import logging
import os
import sys

from aoai_api_simulator.generator.manager import get_default_generators
from aoai_api_simulator.generator.model_catalogue import model_catalogue
from aoai_api_simulator.limiters import get_default_limiters
from aoai_api_simulator.models import Config, OpenAIDeployment
from aoai_api_simulator.record_replay.handler import get_default_forwarders


def get_config_from_env_vars(logger: logging.Logger) -> Config:
    """
    Load configuration from environment variables
    """
    config = Config(generators=get_default_generators())
    config.recording.forwarders = get_default_forwarders()
    config.openai_deployments = _load_openai_deployments(logger)

    if not config.openai_deployments:
        logger.info("OpenAI deployments not set - using default OpenAI deployments")
        config.openai_deployments = _default_openai_deployments()

    initialize_config(config)
    return config


def initialize_config(config: Config):
    config.limiters = get_default_limiters(config)

    # load extension and invoke to update config (customise forwarders, generators, etc.)
    load_extension(config)


def _load_openai_deployments(logger: logging.Logger) -> dict[str, OpenAIDeployment]:
    openai_deployment_config_path = os.getenv("OPENAI_DEPLOYMENT_CONFIG_PATH")

    if not openai_deployment_config_path:
        logger.info("No OpenAI deployment configuration found")
        return None

    if not os.path.isabs(openai_deployment_config_path):
        openai_deployment_config_path = os.path.abspath(openai_deployment_config_path)

    if not os.path.exists(openai_deployment_config_path):
        logger.error("OpenAI deployment configuration file not found: %s", openai_deployment_config_path)
        return None

    with open(openai_deployment_config_path, encoding="utf-8") as f:
        config_json = json.load(f)
    deployments = {}
    for deployment_name, deployment in config_json.items():
        model_name = deployment["model"]

        if model_name not in model_catalogue:
            logger.error(
                "Model %s from deployment %s not supported in the simulator."
                + "Please raise an issue in the aoai_api_simulator repo.",
                model_name,
                deployment_name,
            )

        model = model_catalogue[model_name]
        deployments[deployment_name] = OpenAIDeployment(
            name=deployment_name,
            model=model,
            tokens_per_minute=int(deployment.get("tokensPerMinute", 0)),
            embedding_size=int(deployment.get("embeddingSize", 1536)),
            requests_per_minute=int(deployment.get("requestsPerMinute", 0)),
        )
    return deployments


def _default_openai_deployments() -> dict[str, OpenAIDeployment]:
    # Default set of OpenAI deployment configurations for when none are provided
    embedding_model = model_catalogue["text-embedding-ada-002"]
    gpt_35_turbo_model = model_catalogue["gpt-3.5-turbo"]
    whisper_model = model_catalogue["whisper"]
    return {
        "embedding": OpenAIDeployment(
            name="embedding", model=embedding_model, tokens_per_minute=20000, embedding_size=1536
        ),
        "gpt-35-turbo-1k-token": OpenAIDeployment(
            name="gpt-35-turbo-1k-token", model=gpt_35_turbo_model, tokens_per_minute=1000
        ),
        "gpt-35-turbo-2k-token": OpenAIDeployment(
            name="gpt-35-turbo-2k-token", model=gpt_35_turbo_model, tokens_per_minute=2000
        ),
        "gpt-35-turbo-5k-token": OpenAIDeployment(
            name="gpt-35-turbo-5k-token", model=gpt_35_turbo_model, tokens_per_minute=5000
        ),
        "gpt-35-turbo-10k-token": OpenAIDeployment(
            name="gpt-35-turbo-10k-token", model=gpt_35_turbo_model, tokens_per_minute=10000
        ),
        "gpt-35-turbo-20k-token": OpenAIDeployment(
            name="gpt-35-turbo-20k-token", model=gpt_35_turbo_model, tokens_per_minute=20000
        ),
        "gpt-35-turbo-50k-token": OpenAIDeployment(
            name="gpt-35-turbo-50k-token", model=gpt_35_turbo_model, tokens_per_minute=50000
        ),
        "gpt-35-turbo-100k-token": OpenAIDeployment(
            name="gpt-35-turbo-100k-token", model=gpt_35_turbo_model, tokens_per_minute=100000
        ),
        "gpt-35-turbo-100m-token": OpenAIDeployment(
            name="gpt-35-turbo-100m-token", model=gpt_35_turbo_model, tokens_per_minute=100000000
        ),
        "whisper": OpenAIDeployment(
            name="whisper", model=whisper_model, requests_per_minute=3
        )
    }


def load_extension(config: Config):
    extension_path = config.extension_path
    if not extension_path:
        return

    # extension_path can either be a single python file or the path to a folder with a __init__.py
    # If an __init__.py, use the last folder name as the module name as that is intuitive when the __init__.py
    # references other files in the same folder
    config_is_dir = os.path.isdir(extension_path)
    if config_is_dir:
        module_name = os.path.basename(extension_path)
        path_to_load = os.path.join(extension_path, "__init__.py")
    else:
        module_name = "__extension"
        path_to_load = extension_path

    module_spec = importlib.util.spec_from_file_location(module_name, path_to_load)
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = module
    module_spec.loader.exec_module(module)
    module.initialize(config)


# pylint: disable-next=invalid-name
_config = None


def get_config() -> Config:
    if not _config:
        raise ValueError("Config not set")
    return _config


def set_config(new_config: Config):
    # pylint: disable-next=global-statement
    global _config
    initialize_config(new_config)
    _config = new_config
