# Arches-HQ — Docker build/run helpers.
#
# Targets:
#   build           build the api+gateway runtime image
#   build-web       build the web frontend image
#   up              bring up the full stack (compose)
#   down            tear down the stack
#   logs            tail stack logs
#   ps              show stack status
#   clean           remove built images
#
# Stateful deps (postgres/redis/minio/keycloak) come from infra/docker-compose.yml
# during local dev; docker-compose.yml in this dir is the full production stack.

# Path anchors (independent of where make is invoked from, e.g. `make -C docker`):
#   DOCKER = this Makefile's directory (Dockerfiles + compose file)
#   ROOT   = repo root (required build context)
DOCKER    := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
ROOT      := $(DOCKER)/..

IMAGE     ?= archeshq
TAG       ?= latest
COMPOSE   := docker compose -f $(DOCKER)/docker-compose.yml --env-file $(ROOT)/.env

.PHONY: build build-web up down logs ps clean

build: ## Build the API + agent-gateway runtime image
	docker build -f $(DOCKER)/Dockerfile -t $(IMAGE)-backend:$(TAG) $(ROOT)

build-web: ## Build the web frontend image
	docker build -f $(DOCKER)/Dockerfile.web -t $(IMAGE)-web:$(TAG) $(ROOT)

up: ## Bring up the full stack
	$(COMPOSE) up -d --build

down: ## Stop the stack
	$(COMPOSE) down

logs: ## Tail stack logs
	$(COMPOSE) logs -f

ps: ## Show stack status
	$(COMPOSE) ps

clean: ## Remove built images
	docker rmi $(IMAGE)-backend:$(TAG) $(IMAGE)-web:$(TAG) 2>/dev/null || true
