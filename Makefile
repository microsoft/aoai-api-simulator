SHELL=/bin/bash

ifneq (,$(wildcard ./.env))
    include .env
    export
endif

makefile_dir := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

help: ## Show this help
	@grep -E '[a-zA-Z_-]+:.*?## .*$$' $(firstword $(MAKEFILE_LIST)) \
	| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-32s\033[0m %s\n", $$1, $$2}'

install-requirements: ## Install PyPI requirements for all projects
	pip install -r src/aoai-api-simulator/requirements.txt
	pip install -r loadtest/requirements.txt
	pip install -r tests/requirements.txt
	pip install -r tools/test-client/requirements.txt
	pip install -r tools/test-client-web/requirements.txt
	pip install -r tools/dev-requirements.txt

run-simulated-api: ## Launch the AOAI Simulated API locally
	gunicorn \
		aoai_api_simulator.main:app \
		--worker-class uvicorn.workers.UvicornWorker \
		--workers 1 \
		--bind 0.0.0.0:8000 \
		--timeout 3600

deploy-aca-bicep: ## Run deployment script for Azure Container Apps
	./scripts/deploy-aca-bicep.sh

deploy-aca-terraform: ## Run deployment script for Azure Container Apps
	./scripts/deploy-aca-terraform.sh

test: ## Run PyTest (verbose)
	pytest ./tests -vv

test-not-slow: ## Run PyTest (verbose, skip slow tests)
	pytest ./tests -vv -m "not slow"

test-watch: ## Start PyTest Watch
	ptw --clear ./tests

lint: ## Lint aoai-api-simulator source code
	pylint ./src/aoai-api-simulator/

lint-docs: ## Lint Markdown docs
	docker run -v $$PWD:/workdir ghcr.io/igorshubovych/markdownlint-cli:latest "**/*.md"

run-test-client: ## Run the test client
	cd tools/test-client && \
	python app.py

run-test-client-simulator-local: ## Run the test client against local AOAI Simulated API
	cd tools/test-client && \
	TEST_OPENAI_KEY=${SIMULATOR_API_KEY} \
	TEST_OPENAI_ENDPOINT=http://localhost:8000 \
	TEST_FORM_RECOGNIZER_ENDPOINT=http://localhost:8000 \
	TEST_FORM_RECOGNIZER_KEY=${SIMULATOR_API_KEY} \
	python app.py

run-test-client-simulator-aca: ## Run the test client against an Azure Container Apps deployment
	./scripts/run-test-client-aca.sh

run-test-client-web: ## Launch the test client web app locally
	cd tools/test-client-web && \
	flask run --host 0.0.0.0

docker-build-simulated-api: ## Build the AOAI Simulated API as a docker image
	# TODO should set a tag!
	cd src/aoai-api-simulator && \
	docker build -t aoai-api-simulator .

docker-run-simulated-api: ## Run the AOAI Simulated API docker container
	echo "makefile_dir: ${makefile_dir}"
	echo "makefile_path: ${makefile_path}"
	docker run --rm -i -t \
		-p 8000:8000 \
		-v "${makefile_dir}.recording":/mnt/recording \
		-e RECORDING_DIR=/mnt/recording \
		-e SIMULATOR_MODE \
		-e SIMULATOR_API_KEY \
		-e AZURE_OPENAI_ENDPOINT \
		-e AZURE_OPENAI_KEY \
		-e AZURE_OPENAI_DEPLOYMENT \
		aoai-api-simulator

docker-build-load-test: ## Build the AOAI Simulated API Load Test as a docker image
	# TODO should set a tag!
	cp -R tests/audio loadtest/.audio && \
	cd loadtest && \
	docker build -t aoai-api-simulator-load-test .

erase-recording: ## Erase all *.recording files
	rm -rf "${makefile_dir}.recording"

