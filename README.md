# Fluent Bit + FastAPI Logging Sandbox (Plan)

This plan sets up a minimal, easy-to-run stack to learn Fluent Bit, collect app/process logs, and forward them to a simple destination. We’ll use:

- FastAPI app served by Uvicorn
- Fluent Bit to collect and forward logs
- Docker Compose to orchestrate

We will keep it simple and avoid complex backends like Loki/Grafana. Fluent Bit will forward to a tiny HTTP endpoint (our FastAPI app) or write to a file for easiest verification.

## Goals

- Collect application logs and simple process/system logs.
- Forward logs to the easiest possible destination:
  - Option A (default): HTTP output to the FastAPI app `/ingest` endpoint (acts as a simple log receiver).
  - Option B: File output to a mounted volume for local inspection.
- Run everything with Docker Compose.

## Architecture Overview

- `app` (FastAPI + Uvicorn):
  - Provides a demo API `GET /` returning health payload.
  - Provides a log ingestion endpoint `POST /ingest` that receives batches from Fluent Bit HTTP output and writes them to a file + stdout.
  - Also writes its own application logs to a shared volume (`/logs/app/app.log`) so Fluent Bit can tail those logs.

- `fluent-bit`:
  - Input: `tail` of `/logs/app/app.log` (shared volume).
  - Optional input: `cpu` (demonstrates process/system metrics-style logs).
  - Output (default): `http` to `app:8000/ingest`.
  - Alternative output: `file` to `/logs/collected/`.

- Volumes:
  - `logs_shared`: shared between `app` and `fluent-bit` so Fluent Bit can read app logs and optionally write collected output.

- Networking:
  - Single default Compose network; services discoverable by name. Fluent Bit uses `Host app` to reach the receiver.

References consulted (recent docs):
- Fluent Bit inputs/outputs examples (HTTP, tail, file, stdout): fluent-bit docs.
- Docker Compose best practice: use `compose.yaml`, no `version` key needed on v2+.
- FastAPI minimal app and running with `uvicorn main:app --host 0.0.0.0 --port 8000`.

## Repository Layout (planned)

```
learn_fluentbit/
  app/
    main.py
    requirements.txt
    Dockerfile
  fluent-bit/
    fluent-bit.conf
    parsers.conf   # optional (if we add custom parsers later)
  compose.yaml
  README.md  # this plan
```

We will mount a shared logs directory at runtime:

- Host: `./_data/logs/`
- In containers: `/logs/`

Subpaths used:
- App writes to `/logs/app/app.log`.
- Fluent Bit may also write collected output to `/logs/collected/` if using file output option.

## Docker Compose (plan)

Compose v2+ favors `compose.yaml` without a `version:` key (the CLI determines schema). Service names will be `app` and `fluent-bit`.

High-level compose spec:

- `services.app`
  - build: `./app`
  - command: `uvicorn main:app --host 0.0.0.0 --port 8000`
  - ports: `8000:8000`
  - environment:
    - `APP_LOG_PATH=/logs/app/app.log`
  - volumes: `./_data/logs:/logs`

- `services.fluent-bit`
  - image: `cr.fluentbit.io/fluent/fluent-bit:latest`
  - depends_on: `app`
  - volumes:
    - `./fluent-bit/fluent-bit.conf:/fluent-bit/etc/fluent-bit.conf:ro`
    - `./fluent-bit/parsers.conf:/fluent-bit/etc/parsers.conf:ro` (optional)
    - `./_data/logs:/logs`
  - command: `-c /fluent-bit/etc/fluent-bit.conf`

## Fluent Bit configuration (plan)

We’ll start with the classic `.conf` format for clarity. Two variants are proposed; we’ll set HTTP output as default and leave the file output block commented for easy switch.

- Service settings (flush interval, log level)
- Inputs:
  - `tail` input to read the app’s log file.
    - `Path` = `/logs/app/app.log`
    - `Tag` = `app.log`
    - Optional `Parser` = `json` if app logs JSON; otherwise plain text.
  - `cpu` input to demonstrate a process/metrics-like log stream. Tag `metrics.cpu`.
- Outputs (choose one primary):
  - HTTP output to the receiver in the app:
    - `Host app`, `Port 8000`, `URI /ingest`.
    - `Format json` (default structured JSON lines).
  - File output (alternate for simplest local check):
    - `Path /logs/collected`

Example baseline `fluent-bit.conf` (to be created next):

```
[SERVICE]
    Flush     1
    Log_Level info
    Parsers_File /fluent-bit/etc/parsers.conf

[INPUT]
    Name   tail
    Path   /logs/app/app.log
    Tag    app.log
    Refresh_Interval 1
    Skip_Long_Lines  On

[INPUT]
    Name   cpu
    Tag    metrics.cpu

# Default: forward to HTTP receiver in the app
[OUTPUT]
    Name   http
    Match  *
    Host   app
    Port   8000
    URI    /ingest
    Format json

# Alternate: write to file for easy verification (uncomment to use)
# [OUTPUT]
#     Name   file
#     Match  *
#     Path   /logs/collected
```

Notes:
- If we later emit structured JSON logs from the app, we can add a parser and filters as needed.
- We can also add `[FILTER]` blocks (e.g., `modify`, `record_modifier`, `grep`) if needed.

## App (FastAPI + Uvicorn) plan

- Endpoints:
  - `GET /` returns `{ "status": "ok" }` for health.
  - `POST /ingest` accepts JSON payloads from Fluent Bit’s HTTP output. Fluent Bit batches records (depending on settings); we’ll accept both an array and single JSON object. We’ll append normalized lines to `/logs/received/ingest.log` and also print to stdout.
- Background logging:
  - App writes its own app events to `APP_LOG_PATH` (defaults `/logs/app/app.log`). We’ll log a line every N seconds to simulate application logs.
- Dependencies:
  - `fastapi`
  - `uvicorn`

Example responsibilities in `app/main.py`:
- Read `APP_LOG_PATH` env var, set up a `logging.FileHandler` to write json/plain logs to that path.
- Implement routes.

## Test plan

1) Bring the stack up:
- `docker compose up --build`

2) Generate some app logs:
- Access `http://localhost:8000/` to confirm the app is up (also triggers an app log).
- The app may emit a periodic background log line every few seconds.

3) Verify Fluent Bit is tailing and forwarding:
- If using HTTP output (default):
  - Check `docker compose logs fluent-bit` for output status lines.
  - Check `docker compose logs app` to see the receiver printing received batches.
  - Also check the file `/logs/received/ingest.log` inside the app container or host-mounted `_data/logs/received/ingest.log` if we map it.
- If using File output:
  - Inspect `./_data/logs/collected/` on the host.

4) Explore and extend:
- Add more inputs: `systemd`, `docker` (requires mounting `/var/run/docker.sock`), `tcp`, `http`.
- Add filters: `modify` to add environment labels, `grep` to drop noisy lines, `nest`/`parser` for structure.

## Next steps (implementation checklist)

- Create `app/main.py` with minimal FastAPI app + log receiver + file logger emitting to `/logs/app/app.log`.
- Create `app/requirements.txt` with `fastapi` and `uvicorn`.
- Create `app/Dockerfile`.
- Create `fluent-bit/fluent-bit.conf` (and optional `parsers.conf`).
- Create `compose.yaml`.
- Create local directory `_data/logs/` (with subdirs `app`, `collected`, `received`) or let Compose create via bind mount.
- Run `docker compose up --build` and test.

## Design choices and rationale

- Destination simplicity: HTTP receiver within the same stack is the easiest end-to-end demo and keeps you in full control. File output remains the absolute simplest fallback for verification.
- Compose file format: We’ll use `compose.yaml` with no `version:` key per current Compose v2 practices. Service names `app` and `fluent-bit` are concise and descriptive.
- Tail input vs docker input: Tailing a shared file is simpler to start with and avoids binding the Docker socket. You can switch to `docker` input later for container logs at scale.

## Troubleshooting tips

- If Fluent Bit can’t reach the app: ensure Compose network is up and the service name is `app`, port `8000` is exposed internally.
- If `tail` doesn’t read: confirm the file exists inside the container at `/logs/app/app.log`. Ensure the app creates the file on startup and volumes are correctly mounted.
- Increase verbosity: set `[SERVICE] Log_Level debug` in `fluent-bit.conf`.

---

If this plan looks good, I’ll proceed to implement the files and wire everything up, then run `docker compose up --build` for an end-to-end demo.
