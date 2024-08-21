from aoai_api_simulator.models import Config

from .document_intelligence_forwarder import forward_to_azure_document_intelligence


def initialize(config: Config):
    """initialize is the entry point invoked by the simulator"""

    # Add the forwarder to the config if not already present
    # (NOTE: initialize may be called multiple times)
    if forward_to_azure_document_intelligence not in config.recording.forwarders:
        config.recording.forwarders.append(forward_to_azure_document_intelligence)
