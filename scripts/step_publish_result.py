"""Paso: publica el resultado (vídeo principal + clips) en el propio repo,
para que la página web pueda leerlo y mostrar las miniaturas. La propia
página lo borra en cuanto lo ha leído — este paso solo lo escribe.
"""
from __future__ import annotations

import base64
import json
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(__file__))
from common import env  # noqa: E402

MANIFEST_PATH = "run_data/manifest.json"
RESULT_PATH = "run_data/result.json"
CLIPS_RESULT_PATH = "run_data/clips_result.json"


def load_json(path: str):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def main() -> None:
    result = load_json(RESULT_PATH)
    if not result:
        print("Aviso: no hay resultado de subida que publicar.")
        return
    clips = load_json(CLIPS_RESULT_PATH) or []

    payload = {"main": result, "clips": clips}

    token = env("GITHUB_TOKEN")
    repo = env("GITHUB_REPOSITORY")
    run_id = env("GITHUB_RUN_ID")
    branch = env("GITHUB_REF_NAME") or "main"
    if not token or not repo or not run_id:
        print("Aviso: falta GITHUB_TOKEN, GITHUB_REPOSITORY o GITHUB_RUN_ID; no se publica el resultado.")
        return

    path = f"run_status/{run_id}.json"
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    content_b64 = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")

    try:
        resp = requests.put(
            url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            json={"message": f"chore: publicar resultado ({run_id})", "content": content_b64, "branch": branch},
            timeout=20,
        )
        resp.raise_for_status()
        print(f"Resultado publicado en {path}.")
    except requests.RequestException as exc:
        print(f"Aviso: no se pudo publicar el resultado ({exc}).")


if __name__ == "__main__":
    main()
