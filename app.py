"""Fleet Console — a live web front end for the agent-fleet orchestrator.

Run it:
    python app.py                 # http://localhost:8080
    gunicorn app:app --bind 0.0.0.0:8080
"""

from __future__ import annotations

import os

from flask import Flask, jsonify, render_template, request

from fleet_console import service

MAX_TASK_CHARS = 4_000

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "fleet-console", "version": service.__version__})


@app.get("/api/config")
def config():
    return jsonify(service.describe())


@app.post("/api/run")
def run():
    body = request.get_json(silent=True) or {}
    task = (body.get("task") or "").strip()
    if not task:
        return jsonify({"error": "task is required"}), 400
    if len(task) > MAX_TASK_CHARS:
        return jsonify({"error": f"task exceeds {MAX_TASK_CHARS} characters"}), 400

    chaos = bool(body.get("chaos"))
    return jsonify(service.run_pipeline(task, chaos=chaos))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
