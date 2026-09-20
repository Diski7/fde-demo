# Fleet Console

A **live web console** for the [`agent-fleet`](https://github.com/Diski7/agent-fleet) orchestrator.

Give it a task, and watch three agents run in sequence — with the routing
decisions, fallback attempts, guardrail outcomes and cost reported for the
**whole run**, not just the final string.

```
classifier ──▶ researcher ──▶ writer
   (cheap)        (cheap)      (frontier)
```

---

## Why this exists

A framework that only runs in someone's terminal is not proof of anything. This
is the part that makes it **usable and inspectable**: every routing hop is
visible, the fallback chain can be triggered on demand, and the cost of
reliability is a number on the screen instead of a claim in a README.

---

## Quick start

```bash
pip install -r requirements.txt
python app.py
# open http://localhost:8080
```

With Docker:

```bash
docker build -t fleet-console .
docker run --rm -p 8080:8080 fleet-console
```

---

## What you can do in the UI

| Action | What it shows |
|---|---|
| **Run the fleet** | The full three-stage pipeline with per-stage model, attempts and cost |
| **Take the cheap model offline** | The same run where the cheap model fails — the fallback chain advances, the run still succeeds, and the extra cost is reported against a healthy baseline |
| **Try a prompt injection** | A guardrail blocks the request *before* any model call; the trace shows zero stages run |
| **Try a leaked key** | A key-shaped string is redacted from the prompt — the call proceeds, the secret does not |

---

## The interesting part: what fallback costs

Flip the chaos switch and the summary grows a comparison card:

```
attempts            8
failures            2
cost                $0.001470
baseline            $0.000663        (+$0.000807)
```

Reliability is not free, and now it has a price tag. That number is produced by
running the *same task twice* — once with the cheap model healthy, once without
— so the delta is measured, not estimated.

In this run both `classifier` and `researcher` lost their first attempt to the
offline cheap model and landed on the frontier model on attempt 2; `writer`
started on the frontier and never failed. The run succeeded, cost 2.2× the
baseline, and the two failed attempts are still visible in the trace.

---

## Guardrails run before the model, not after

The framework enforces these on every call:

| Guardrail | Behaviour |
|---|---|
| **Length** | Inputs over 50,000 characters are blocked |
| **Prompt injection** | Known override patterns are blocked |
| **Secret redaction** | Key-shaped strings are scrubbed, not rejected |

Because they run *before* the call, a blocked request costs nothing and leaks
nothing. The trace makes that visible: a blocked run contains no model spans at
all.

---

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | The console |
| `GET` | `/api/health` | Liveness |
| `GET` | `/api/config` | Routes, roles and guardrails |
| `POST` | `/api/run` | `{"task": "...", "chaos": false}` |

---

## Design notes

- **Deterministic by default.** The provider is a mock, so the demo runs offline
  with no API keys and produces the same trace every time. That makes it a demo
  people can actually run, and tests that assert on real numbers instead of
  vibes.
- **One tracer per run, not per call.** The summary is only meaningful because
  all three stages report into the same tracer.
- **No build step.** Vanilla HTML/JS/CSS. `curl` the API if you prefer.
- **Framework from GitHub.** `requirements.txt` pins `agent-fleet` to the repo,
  so the console can never drift from the framework it demonstrates.

---

## Tests

```bash
pytest        # service-layer and HTTP-layer suites
```

---

## Licence

MIT
