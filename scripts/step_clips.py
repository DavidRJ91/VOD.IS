"""Paso: crea hasta CLIP_COUNT clips de ~30s repartidos por el VOD y los
deja en el propio repositorio para que la web los ofrezca como descarga.
No se suben a YouTube. Es un extra — si un clip falla, se avisa y se sigue
con los demás; nunca tumba la subida del vídeo principal, que ya ocurrió
antes.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys

import requests

sys.path.insert(0, os.path.dirname(__file__))
from common import env  # noqa: E402

MANIFEST_PATH = "run_data/manifest.json"
CLIPS_RESULT_PATH = "run_data/clips_result.json"
CLIP_DURATION_SECONDS = 30
CLIPS_DIR = "clips"
MAX_CLIPS = 10


def compute_clip_starts(count: int, duration: float) -> list[float]:
    """Reparte 'count' instantes de inicio a lo largo del vídeo, dejando un
    margen al principio y al final para no caer en intro/outro ni cortarse."""
    if count <= 0 or duration <= CLIP_DURATION_SECONDS:
        return []
    margin = min(duration * 0.05, 60)
    usable_start = margin
    usable_end = max(duration - margin - CLIP_DURATION_SECONDS, usable_start)
    if usable_end <= usable_start:
        return [max((duration - CLIP_DURATION_SECONDS) / 2, 0)]
    if count == 1:
        return [usable_start + (usable_end - usable_start) / 2]
    step = (usable_end - usable_start) / (count - 1)
    return [usable_start + step * i for i in range(count)]


def extract_clip(video_path: str, start_seconds: float, output_path: str) -> bool:
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", str(start_seconds),
                "-i", video_path,
                "-t", str(CLIP_DURATION_SECONDS),
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-c:a", "aac",
                "-movflags", "+faststart",
                output_path,
            ],
            check=True,
            capture_output=True,
        )
        return os.path.exists(output_path)
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"Aviso: no se pudo extraer el clip en {start_seconds:.0f}s ({exc}); se omite.")
        return False


def commit_clip_to_repo(clip_path: str, repo_path: str) -> str | None:
    """Sube el clip al propio repositorio (para que la web lo pueda ofrecer
    como descarga) y devuelve el sha del blob, o None si falla."""
    token = env("GITHUB_TOKEN")
    repo = env("GITHUB_REPOSITORY")
    branch = env("GITHUB_REF_NAME") or "main"
    if not token or not repo:
        print("Aviso: falta GITHUB_TOKEN o GITHUB_REPOSITORY; no se puede publicar el clip.")
        return None

    with open(clip_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode("ascii")

    url = f"https://api.github.com/repos/{repo}/contents/{repo_path}"
    try:
        resp = requests.put(
            url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            json={"message": f"chore: publicar clip ({repo_path})", "content": content_b64, "branch": branch},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["content"]["sha"]
    except requests.RequestException as exc:
        print(f"Aviso: no se pudo publicar el clip en el repo ({exc}); se omite.")
        return None


def main() -> None:
    clip_count = min(int(env("CLIP_COUNT", "0") or 0), MAX_CLIPS)
    if clip_count <= 0:
        print("No se pidieron clips.")
        return

    if not os.path.exists(MANIFEST_PATH):
        print("Aviso: no hay manifiesto de descarga; se omiten los clips.")
        return
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    duration = manifest.get("duration") or 0
    starts = compute_clip_starts(clip_count, duration)
    if not starts:
        print("Aviso: el VOD es demasiado corto para sacar clips de 30s; se omiten.")
        return

    os.makedirs(CLIPS_DIR, exist_ok=True)
    run_id = env("GITHUB_RUN_ID") or "local"

    clips_result = []
    for i, start in enumerate(starts, start=1):
        clip_path = os.path.join(CLIPS_DIR, f"clip-{i}.mp4")
        print(f"Extrayendo clip {i}/{len(starts)} en el segundo {start:.0f}…")
        if not extract_clip(manifest["filepath"], start, clip_path):
            continue

        repo_path = f"clip_output/{run_id}/clip-{i}.mp4"
        size_bytes = os.path.getsize(clip_path)
        sha = commit_clip_to_repo(clip_path, repo_path)
        if sha:
            clips_result.append({
                "repo_path": repo_path,
                "sha": sha,
                "start_seconds": round(start),
                "size_bytes": size_bytes,
            })
            print(f"Clip {i} publicado en el repo ({size_bytes / (1024 * 1024):.1f} MB).")
        if os.path.exists(clip_path):
            os.remove(clip_path)

    with open(CLIPS_RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(clips_result, f, ensure_ascii=False)

    print(f"{len(clips_result)} de {len(starts)} clips publicados correctamente.")


if __name__ == "__main__":
    main()
