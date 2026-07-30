"""Paso: sube el vídeo principal a YouTube y le aplica la portada preparada.

No hay navegador disponible dentro de GitHub Actions, así que la autenticación
usa un refresh token generado una sola vez, localmente, con
scripts/get_refresh_token.py.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import die, env  # noqa: E402
from youtube_common import YouTubeError, get_authenticated_service, set_thumbnail, upload_video  # noqa: E402

MANIFEST_PATH = "run_data/manifest.json"
RESULT_PATH = "run_data/result.json"


def main() -> None:
    if not os.path.exists(MANIFEST_PATH):
        die("No se encontró el manifiesto de descarga (¿falló el paso anterior?).")
        return
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    title = env("VIDEO_TITLE") or manifest["title"]
    description = env("VIDEO_DESCRIPTION") or manifest["description"]

    try:
        youtube = get_authenticated_service()
        video_id = upload_video(
            youtube,
            filepath=manifest["filepath"],
            title=title,
            description=description,
            tags=[],
            category_id=env("YOUTUBE_CATEGORY_ID") or "20",
            privacy=env("PRIVACY", "unlisted"),
            scheduled_at=env("SCHEDULED_AT"),
        )
        if set_thumbnail(youtube, video_id, manifest.get("thumbnail_path")):
            print("Portada aplicada.")
    except YouTubeError as exc:
        die(str(exc))
        return

    result = {
        "video_id": video_id,
        "video_url": f"https://youtu.be/{video_id}",
        "title": title,
        "source_url": manifest["source_url"],
        "privacy": env("PRIVACY", "unlisted"),
    }
    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)

    print(f"Subido: {result['video_url']}")


if __name__ == "__main__":
    main()
