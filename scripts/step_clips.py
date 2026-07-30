"""Paso: crea hasta CLIP_COUNT clips de ~30s repartidos por el VOD y los
sube a YouTube. Es un extra — si un clip falla, se avisa y se sigue con
los demás; nunca tumba la subida del vídeo principal, que ya ocurrió antes.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import env  # noqa: E402
from youtube_common import YouTubeError, get_authenticated_service, upload_video  # noqa: E402

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
                "-c:v", "libx264", "-c:a", "aac",
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
    base_title = env("VIDEO_TITLE") or manifest.get("title") or "Vídeo"
    base_description = env("VIDEO_DESCRIPTION") or manifest.get("description") or ""
    privacy = env("PRIVACY", "unlisted")
    scheduled_at = env("SCHEDULED_AT")

    try:
        youtube = get_authenticated_service()
    except YouTubeError as exc:
        print(f"Aviso: no se pudieron subir los clips ({exc}).")
        return

    clips_result = []
    for i, start in enumerate(starts, start=1):
        clip_path = os.path.join(CLIPS_DIR, f"clip-{i}.mp4")
        print(f"Extrayendo clip {i}/{len(starts)} en el segundo {start:.0f}…")
        if not extract_clip(manifest["filepath"], start, clip_path):
            continue
        try:
            video_id = upload_video(
                youtube,
                filepath=clip_path,
                title=f"{base_title} — Clip {i}"[:100],
                description=base_description,
                tags=[],
                category_id=env("YOUTUBE_CATEGORY_ID") or "20",
                privacy=privacy,
                scheduled_at=scheduled_at,
            )
            clips_result.append({
                "video_id": video_id,
                "video_url": f"https://youtu.be/{video_id}",
                "start_seconds": round(start),
            })
            print(f"Clip {i} subido: https://youtu.be/{video_id}")
        except YouTubeError as exc:
            print(f"Aviso: no se pudo subir el clip {i} ({exc}); se omite.")
        finally:
            if os.path.exists(clip_path):
                os.remove(clip_path)

    with open(CLIPS_RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(clips_result, f, ensure_ascii=False)

    print(f"{len(clips_result)} de {len(starts)} clips subidos correctamente.")


if __name__ == "__main__":
    main()
