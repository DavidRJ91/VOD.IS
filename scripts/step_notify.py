"""Paso 3 del workflow: notifica en Discord el resultado (éxito o fallo) y
deja constancia en el historial de la página (run_status/history.json)."""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import append_history_entry, env, notify_discord  # noqa: E402

MANIFEST_PATH = "run_data/manifest.json"
RESULT_PATH = "run_data/result.json"
CLIPS_RESULT_PATH = "run_data/clips_result.json"


def load_json(path: str):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def main() -> None:
    outcome = sys.argv[1] if len(sys.argv) > 1 else "failure"
    manifest = load_json(MANIFEST_PATH) or {}
    result = load_json(RESULT_PATH) or {}
    clips = load_json(CLIPS_RESULT_PATH) or []
    vod_url = manifest.get("source_url") or env("VOD_URL") or "desconocido"
    title = result.get("title") or manifest.get("title") or vod_url

    history_entry = {
        "run_id": env("GITHUB_RUN_ID"),
        "timestamp": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "outcome": outcome,
        "vod_url": vod_url,
        "title": title,
        "clip_count": len(clips),
    }

    if outcome == "success" and result:
        history_entry["video_url"] = result.get("video_url")
        history_entry["privacy"] = result.get("privacy")

        fields = [
            {"name": "Origen", "value": result.get("source_url", vod_url), "inline": False},
            {"name": "YouTube", "value": result["video_url"], "inline": False},
            {"name": "Visibilidad", "value": result.get("privacy", ""), "inline": True},
        ]
        if clips:
            fields.append({
                "name": f"Clips ({len(clips)})",
                "value": "Listos para descargar desde la propia página web (no se suben a YouTube).",
                "inline": False,
            })
        notify_discord(
            {
                "title": "Subida completada",
                "description": f"**{title}**",
                "color": 0x1D9E75,
                "fields": fields,
            }
        )
    else:
        run_url = f"{env('GITHUB_SERVER_URL')}/{env('GITHUB_REPOSITORY')}/actions/runs/{env('GITHUB_RUN_ID')}"
        history_entry["run_url"] = run_url
        notify_discord(
            {
                "title": "Fallo en la subida",
                "description": f"**{title}**",
                "color": 0xE24B4A,
                "fields": [
                    {"name": "Origen", "value": vod_url, "inline": False},
                    {"name": "Registro", "value": run_url, "inline": False},
                ],
            }
        )

    append_history_entry(history_entry)


if __name__ == "__main__":
    main()
