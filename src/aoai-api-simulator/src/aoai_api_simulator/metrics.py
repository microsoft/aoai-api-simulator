from dataclasses import dataclass
from opentelemetry import metrics


@dataclass
class SimulatorMetrics:
    histogram_latency_base: metrics.Histogram
    histogram_latency_full: metrics.Histogram
    histogram_tokens_used: metrics.Histogram
    histogram_tokens_requested: metrics.Histogram
    histogram_tokens_rate_limit: metrics.Histogram
    histogram_rate_limit: metrics.Histogram


def _get_simulator_metrics() -> SimulatorMetrics:
    meter = metrics.get_meter(__name__)
    return SimulatorMetrics(
        # dimensions: deployment, status_code
        histogram_latency_base=meter.create_histogram(
            name="aoai-api-simulator.latency.base",
            description="Latency of handling the request (before adding simulated latency)",
            unit="seconds",
        ),
        # dimensions: deployment, status_code
        histogram_latency_full=meter.create_histogram(
            name="aoai-api-simulator.latency.full",
            description="Full latency of handling the request (including simulated latency)",
            unit="seconds",
        ),
        # dimensions: deployment, token_type
        histogram_tokens_used=meter.create_histogram(
            name="aoai-api-simulator.tokens.used",
            description="Number of tokens used per request",
            unit="tokens",
        ),
        # dimensions: deployment, token_type
        histogram_tokens_requested=meter.create_histogram(
            name="aoai-api-simulator.tokens.requested",
            description="Number of tokens across all requests (success or not)",
            unit="tokens",
        ),
        # dimensions: deployment
        histogram_tokens_rate_limit=meter.create_histogram(
            name="aoai-api-simulator.tokens.rate-limit",
            description="Number of tokens that were counted for rate-limiting",
            unit="tokens",
        ),
        # dimensions: deployment, reason
        histogram_rate_limit=meter.create_histogram(
            name="aoai-api-simulator.limits",
            description="Number of requests that were rate-limited",
            unit="requests",
        ),
    )


simulator_metrics = _get_simulator_metrics()
