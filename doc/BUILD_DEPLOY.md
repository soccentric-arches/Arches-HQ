# Arches-HQ Build and Deployment

## 1. Purpose and scope

Arches-HQ is a local multi-service control plane: Python API and agent gateway, a Vue/Vite web frontend, and Docker Compose services for Postgres, MinIO, and Redis. The root Makefile orchestrates the complete developer stack.

## 2. Prerequisites

`make doctor` checks Docker, Python 3, and Node. Install Docker Compose support, Python virtualenv support, Node/npm, and curl. The Makefile's defaults use local development credentials and persistent Docker volumes; replace them for any shared environment.

## 3. Setup

Run `make doctor`, then `make install` to create `.venv`, install editable `api[dev]` and `agent-gateway[dev]`, and install web dependencies. `make db-up` starts dependencies, creates the test database and MinIO bucket, and waits for Keycloak readiness. Run `make migrate` for Alembic migrations and `make seed EMAIL=you@example.com` to seed a development tenant/admin.

## 4. Build and compile

`make build` runs `npm run build` in `web` and creates the production frontend output in `web/dist`. The Python services are run from the venv rather than compiled into a package by this Makefile.

## 5. Test and lint

- `make test-api` runs API pytest with `ARCHESHQ_TEST_DATABASE_URL` and `ARCHESHQ_S3_ENDPOINT_URL`.
- `make test-gateway` runs agent-gateway pytest with the same service settings.
- `make test-web` runs `npx vitest run`.
- `make test` runs all three suites.
- `make lint-api` and `make lint-gateway` run Ruff.
- `make lint-web` runs npm lint and `vue-tsc --noEmit`.
- `make lint` runs all lint targets.

## 6. Packaging and artifacts

The web artifact is `web/dist`. Local service logs and PID files are stored under `.run`; database and object-store data persist in the Compose volumes declared in `infra/docker-compose.yml`. No image build or registry-publish target exists in this Makefile.

## 7. Deployment, install, and run

- `make run` starts the Compose dependencies, applies migrations, then launches API on port `8000`, web on `5173`, and the gateway on gRPC port `50051`.
- `make logs` tails API, gateway, and web logs.
- `make stop` stops the background application processes but leaves Docker dependencies running.
- `make db-down` stops Compose dependencies; volumes persist.

The stack prints a LAN URL and development login credentials. These are conditional development values only. Cloud deployment, production secrets, TLS, and registry credentials are outside this Makefile and require an environment-specific deployment system.

## 8. Cleanup

`make clean` removes the venv, `.run`, `web/node_modules`, `web/dist`, caches, and Python build caches. Use `make db-down` to stop containers; remove persistent volumes only through an explicit Compose volume cleanup decision.

## 9. Hardware, cloud, and manual verification caveats

HQ can run without target hardware, but end-to-end device workflows require a reachable gateway/server and correctly configured database, and object storage. Use the LAN URL consistently during login. Manual verification should cover username/password login, API authorization, MinIO uploads, SSE/gateway behavior, and service restart recovery.
