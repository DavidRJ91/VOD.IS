"""Paso 3 del workflow: notifica en Discord el resultado (éxito o fallo)."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import env, notify_discord  # noqa: E402

MANIFEST_PATH = "run_data/manifest.json"
RESULT_PATH = "run_data/result.json"


def load_json(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def main() -> None:
    outcome = sys.argv[1] if len(sys.argv) > 1 else "failure"
    manifest = load_json(MANIFEST_PATH)
    result = load_json(RESULT_PATH)
    vod_url = manifest.get("source_url") or env("VOD_URL") or "desconocido"
    title = result.get("title") or manifest.get("title") or vod_url

    if outcome == "success" and result:
        notify_discord(
            {
                "title": "Subida completada",
                "description": f"**{title}**",
                "color": 0x1D9E75,
                "fields": [
                    {"name": "Origen", "value": result.get("source_url", vod_url), "inline": False},
                    {"name": "YouTube", "value": result["video_url"], "inline": False},
                    {"name": "Visibilidad", "value": result.get("privacy", ""), "inline": True},
                ],
            }
        )
    else:
        run_url = f"{env('GITHUB_SERVER_URL')}/{env('GITHUB_REPOSITORY')}/actions/runs/{env('GITHUB_RUN_ID')}"
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


if __name__ == "__main__":
    main()
