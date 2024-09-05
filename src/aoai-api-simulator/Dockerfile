ARG network_type=unrestricted
ARG TIKTOKEN_CACHE_PATH=/app/tiktoken_cache

FROM python:3.12.1-slim-bullseye AS base
WORKDIR /app

FROM base AS simulator-unrestricted-network

# Install gcc and python3-dev to support ARM architecture
RUN apt-get update && apt-get install -y gcc python3-dev

COPY ./requirements.txt ./
RUN pip install -r requirements.txt

COPY . .
RUN pip install .

FROM simulator-unrestricted-network AS simulator-semi-restricted-network
ARG TIKTOKEN_CACHE_PATH
RUN echo "Running semi-restricted network build steps."

ADD https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken ${TIKTOKEN_CACHE_PATH}/9b5ad71b2ce5302211f9c61530b329a4922fc6a4
ENV TIKTOKEN_CACHE_DIR=${TIKTOKEN_CACHE_PATH}

FROM simulator-unrestricted-network AS simulator-restricted-network
ARG TIKTOKEN_CACHE_PATH
RUN echo "Running restricted network build steps."

COPY tiktoken_cache ${TIKTOKEN_CACHE_PATH}
ENV TIKTOKEN_CACHE_DIR=${TIKTOKEN_CACHE_PATH}

FROM simulator-${network_type}-network AS final
CMD [ "gunicorn", "aoai_api_simulator.main:app", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]