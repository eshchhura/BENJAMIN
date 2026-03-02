# BENJAMIN Operational Runbook

## Quickstart (single GPU)

1. Install dependencies:

   ```bash
   python -m pip install -e .[dev]
   ```

2. Set local development environment variables (sample):

   ```bash
   export BENJAMIN_STATE_DIR="$PWD/.state"
   export BENJAMIN_AUTH_MODE=off
   export BENJAMIN_GOOGLE_ENABLED=off

   export BENJAMIN_LLM_PROVIDER=vllm
   export BENJAMIN_LLM_MODEL=zai-org/GLM-4.7
   export BENJAMIN_VLLM_URL=http://127.0.0.1:8001/v1/chat/completions

   export BENJAMIN_LLM_PLANNER=on
   export BENJAMIN_LLM_SUMMARIZER=on
   export BENJAMIN_LLM_DRAFTER=on
   export BENJAMIN_LLM_RULE_BUILDER=on
   export BENJAMIN_LLM_RETRIEVAL=on

   # Optional: let dev runner launch vLLM too.
   export BENJAMIN_DEV_START_VLLM=on
   export BENJAMIN_DEV_VLLM_CMD='vllm serve "$BENJAMIN_LLM_MODEL" --host 127.0.0.1 --port 8001 --dtype auto --max-model-len 8192 --gpu-memory-utilization 0.90'
   ```

3. Validate your environment:

   ```bash
   python scripts/check.py
   ```

4. Start all local services:

   ```bash
   sh scripts/dev.sh
   ```

   On Windows PowerShell:

   ```powershell
   .\scripts\dev.ps1
   ```

> If `scripts/dev.sh` is not executable, run `chmod +x scripts/dev.sh scripts/check.py`.

## One-command dev runner

Both runners perform the same sequence:

1. Run `scripts/check.py`.
2. Optionally start vLLM if:
   - `BENJAMIN_LLM_PROVIDER=vllm`
   - `BENJAMIN_DEV_START_VLLM=on`
   - `BENJAMIN_DEV_VLLM_CMD` is set
3. Start:
   - `benjamin-api`
   - `benjamin-worker`
4. Print:
   - started process list + PIDs
   - API/UI URLs
   - integrations status endpoint
   - vLLM endpoint (if provider is `vllm`)
   - LLM feature flags
   - state directory path

Ctrl+C stops all children (best effort).

## Running services manually

### API only

```bash
benjamin-api
```

### Worker only

```bash
benjamin-worker
```

### vLLM only

```bash
vllm serve "$BENJAMIN_LLM_MODEL" --host 127.0.0.1 --port 8001 --dtype auto --max-model-len 8192 --gpu-memory-utilization 0.90
```

## Health/readiness endpoints

- Basic: `GET /healthz`
- Full readiness snapshot: `GET /healthz/full`
- Integrations status: `GET /integrations/status`

## Recommended env vars for local development

Use this baseline for easiest local startup:

```bash
export BENJAMIN_STATE_DIR="$PWD/.state"
export BENJAMIN_AUTH_MODE=off
export BENJAMIN_GOOGLE_ENABLED=off
export BENJAMIN_RULES_ENABLED=off
export BENJAMIN_DEV_EXPECT_WORKER=on
```

If you enable auth:

```bash
export BENJAMIN_AUTH_MODE=token
export BENJAMIN_AUTH_TOKEN=dev-token
```

## Troubleshooting

### vLLM OOM / startup failures

- Reduce `--max-model-len`.
- Lower `--gpu-memory-utilization`.
- Try quantization options supported by your setup.
- Confirm `BENJAMIN_VLLM_URL` points to the correct host/port/path.

### Missing auth token

If `BENJAMIN_AUTH_MODE=token`, you must set `BENJAMIN_AUTH_TOKEN`.
For local-only iteration, use `BENJAMIN_AUTH_MODE=off`.

### Google token missing

If `BENJAMIN_GOOGLE_ENABLED=on`, ensure `BENJAMIN_GOOGLE_TOKEN_PATH` exists.
Otherwise disable integrations with `BENJAMIN_GOOGLE_ENABLED=off`.

### Auth lockout in UI/API

- Verify `BENJAMIN_AUTH_MODE` is what you expect.
- For token mode, provide `X-BENJAMIN-TOKEN` or use `/ui/login`.
- For local development, temporarily set `BENJAMIN_AUTH_MODE=off`.


## State integrity checks (Ops Doctor)

Run checks against persisted state files:

```bash
python scripts/doctor.py
```

Repair JSONL corruption safely (creates backups, atomic replace):

```bash
python scripts/doctor.py --repair
```

Compact retained JSONL history conservatively using configured limits:

```bash
python scripts/doctor.py --compact
```

