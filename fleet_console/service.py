"""Service layer: wires the agent-fleet framework into a web-facing API.

This is the part that makes the framework *usable* by a person: a task goes
in, and the routing decisions, fallback behaviour, guardrail outcomes and
cost come back out — for the whole run, not just the final string.
"""

from __future__ import annotations

from typing import Any

from agent_fleet import (
    FallbackChain,
    Fleet,
    MockProvider,
    ModelSpec,
    Role,
    Router,
    ToolSpec,
)
from agent_fleet.tracing import Tracer

__version__ = "1.0.0"

# --- pricing, kept explicit so every run reports a real number ---------------

CHEAP = ModelSpec("cheap-mini", cost_per_1k_in=0.0001, cost_per_1k_out=0.0002)
FRONTIER = ModelSpec("frontier", cost_per_1k_in=0.003, cost_per_1k_out=0.015)
LOCAL = ModelSpec("fallback-local", cost_per_1k_in=0.0, cost_per_1k_out=0.0)

#: the model the chaos switch takes offline
CHAOS_MODEL = CHEAP.name

#: ordered pipeline: (role name, task type)
STAGES: list[tuple[str, str]] = [
    ("classifier", "classify"),
    ("researcher", "research"),
    ("writer", "generate"),
]


def build_router() -> Router:
    """Cheap work goes to the cheap model; generation starts at the frontier.

    Every chain has somewhere to go. That is the whole point: a model being
    unavailable degrades quality or cost, never the run.
    """
    return Router(
        routes={
            "classify": FallbackChain([CHEAP, FRONTIER]),
            "research": FallbackChain([CHEAP, FRONTIER]),
            "generate": FallbackChain([FRONTIER, CHEAP, LOCAL]),
        },
        default=FallbackChain([CHEAP, LOCAL]),
    )


def build_roles() -> dict[str, Role]:
    """Declarative roles: instructions, a scoped tool belt, a routing hint."""
    search = ToolSpec(
        "search", "search public sources", lambda q: [f"result for {q}"], scopes=("read",)
    )
    fetch = ToolSpec(
        "fetch", "fetch a document", lambda url: f"content of {url}", scopes=("read",)
    )
    return {
        "classifier": Role(
            name="classifier",
            instructions="Classify the incoming request into a workflow type.",
            model_hint="classify",
        ),
        "researcher": Role(
            name="researcher",
            instructions="Gather sources and extract the key facts.",
            tools=[search, fetch],
            model_hint="research",
        ),
        "writer": Role(
            name="writer",
            instructions="Write a concise, sourced brief from the research notes.",
            model_hint="generate",
        ),
    }


def _run(task: str, chaos: bool) -> tuple[list[dict[str, Any]], Tracer]:
    """Run the pipeline, feeding each stage's output into the next.

    One tracer is shared across all three stages, which is what makes the run
    summary a *run* summary instead of three unrelated per-call numbers.
    """
    provider = MockProvider(fail_models={CHAOS_MODEL} if chaos else None)
    fleet = Fleet(provider, build_router())
    roles = build_roles()
    tracer = Tracer()
    stages: list[dict[str, Any]] = []

    current = task
    for name, task_type in STAGES:
        result, _ = fleet.run(roles[name], current, task_type=task_type, tracer=tracer)
        stage = result.as_dict()
        stage["task_type"] = task_type
        stage["input"] = current
        stages.append(stage)
        if not result.ok:
            break
        current = result.text

    return stages, tracer


def run_pipeline(task: str, chaos: bool = False) -> dict[str, Any]:
    """Run the three-stage pipeline and return results, trace and summary."""
    stages, tracer = _run(task, chaos)
    payload: dict[str, Any] = {
        "task": task,
        "chaos": chaos,
        "stages": stages,
        "summary": tracer.summary(),
        "spans": [s.as_dict() for s in tracer.spans],
    }
    if chaos:
        # same task, healthy models: the delta is what fallback actually costs
        _, base_tracer = _run(task, False)
        payload["baseline_summary"] = base_tracer.summary()
    return payload


def describe() -> dict[str, Any]:
    """Static description of the wiring, for the UI's 'how it is set up' panel."""
    router = build_router()
    return {
        "version": __version__,
        "routes": {t: [m.name for m in chain] for t, chain in router.routes.items()},
        "roles": [
            {
                "name": r.name,
                "instructions": r.instructions,
                "tools": r.tool_names(),
                "model_hint": r.model_hint,
            }
            for r in build_roles().values()
        ],
        "chaos_model": CHAOS_MODEL,
        "guardrails": [
            "length: input capped at 50,000 characters",
            "prompt-injection: known override patterns blocked before the call",
            "secret-redaction: key-shaped strings scrubbed before the call",
        ],
    }
