"""Paso 2 del workflow: sube el vídeo descargado a YouTube.

No hay navegador disponible dentro de GitHub Actions, así que la autenticación
usa un refresh token generado una sola vez, localmente, con
scripts/get_refresh_token.py.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

sys.path.insert(0, os.path.dirname(__file__))
from common import die, env  # noqa: E402

MANIFEST_PATH = "run_data/manifest.json"
RESULT_PATH = "run_data/result.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def privacy_status_and_publish_at(privacy: str, scheduled_at: str):
    if privacy == "public":
        return "public", None
    if privacy == "unlisted":
        return "unlisted", None
    if privacy == "scheduled":
        if not scheduled_at:
            raise ValueError("Falta scheduled_at para privacy=scheduled.")
        dt.datetime.strptime(scheduled_at, "%Y-%m-%dT%H:%M:%SZ")  # valida el formato
        # YouTube exige privacyStatus=private + publishAt para programar;
        # lo pasa a público automáticamente en esa fecha y hora.
        return "private", scheduled_at
    raise ValueError(f"Privacidad desconocida: {privacy}")


def main() -> None:
    if not os.path.exists(MANIFEST_PATH):
        die("No se encontró el manifiesto de descarga (¿falló el paso anterior?).")
        return
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    title = env("VIDEO_TITLE") or manifest["title"]
    description = env("VIDEO_DESCRIPTION") or manifest["description"]

    try:
        privacy_status, publish_at = privacy_status_and_publish_at(
            env("PRIVACY", "unlisted"), env("SCHEDULED_AT")
        )
    except ValueError as exc:
        die(str(exc))
        return

    creds = Credentials(
        None,
        refresh_token=env("YOUTUBE_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=env("YOUTUBE_CLIENT_ID"),
        client_secret=env("YOUTUBE_CLIENT_SECRET"),
        scopes=SCOPES,
    )
    try:
        creds.refresh(Request())
    except Exception as exc:  # noqa: BLE001
        die(f"No se pudo renovar la sesión de YouTube: {exc}")
        return

    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": [],
            "categoryId": env("YOUTUBE_CATEGORY_ID") or "20",
        },
        "status": {"privacyStatus": privacy_status, "selfDeclaredMadeForKids": False},
    }
    if publish_at:
        body["status"]["publishAt"] = publish_at

    media = MediaFileUpload(
        manifest["filepath"], chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/*"
    )
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    try:
        while response is None:
            _, response = request.next_chunk()
    except HttpError as exc:
        die(f"Error de la API de YouTube: {exc}")
        return

    video_id = response["id"]

    thumbnail_path = manifest.get("thumbnail_path")
    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg"),
            ).execute()
            print("Portada aplicada.")
        except HttpError as exc:
            print(
                "Aviso: no se pudo aplicar la portada — comprueba que tu canal esté "
                f"verificado en youtube.com/verify. Detalle: {exc}"
            )

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
