"""Lógica compartida de YouTube: autenticación, subida de vídeo y portada.

Usado tanto por step_upload.py (el VOD completo) como por step_clips.py
(los clips cortos) y por los pasos de grabación de directos, para no
duplicar la parte de autenticación/subida.
"""
from __future__ import annotations

import datetime as dt
import os
from typing import List, Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from common import env

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class YouTubeError(Exception):
    pass


def get_authenticated_service():
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
        raise YouTubeError(f"No se pudo renovar la sesión de YouTube: {exc}") from exc
    return build("youtube", "v3", credentials=creds)


def privacy_status_and_publish_at(privacy: str, scheduled_at: str) -> Tuple[str, Optional[str]]:
    if privacy == "public":
        return "public", None
    if privacy == "unlisted":
        return "unlisted", None
    if privacy == "scheduled":
        if not scheduled_at:
            raise YouTubeError("Falta scheduled_at para privacy=scheduled.")
        dt.datetime.strptime(scheduled_at, "%Y-%m-%dT%H:%M:%SZ")  # valida el formato
        # YouTube exige privacyStatus=private + publishAt para programar;
        # lo pasa a público automáticamente en esa fecha y hora.
        return "private", scheduled_at
    raise YouTubeError(f"Privacidad desconocida: {privacy}")


def upload_video(
    youtube,
    filepath: str,
    title: str,
    description: str,
    tags: List[str],
    category_id: str,
    privacy: str,
    scheduled_at: Optional[str] = None,
) -> str:
    """Sube un archivo de vídeo y devuelve el video_id resultante."""
    privacy_status, publish_at = privacy_status_and_publish_at(privacy, scheduled_at)

    body = {
        "snippet": {
            "title": (title or "Vídeo")[:100],
            "description": (description or "")[:5000],
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {"privacyStatus": privacy_status, "selfDeclaredMadeForKids": False},
    }
    if publish_at:
        body["status"]["publishAt"] = publish_at

    if not os.path.exists(filepath):
        raise YouTubeError(f"No se encuentra el archivo a subir: {filepath}")

    media = MediaFileUpload(filepath, chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/*")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    try:
        while response is None:
            _, response = request.next_chunk()
    except HttpError as exc:
        raise YouTubeError(f"Error de la API de YouTube al subir «{title}»: {exc}") from exc

    return response["id"]


def set_thumbnail(youtube, video_id: str, thumbnail_path: str) -> bool:
    """Intenta poner la portada; un fallo aquí no debe tumbar la subida ya hecha."""
    if not thumbnail_path or not os.path.exists(thumbnail_path):
        return False
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg"),
        ).execute()
        return True
    except HttpError as exc:
        print(
            "Aviso: no se pudo aplicar la portada — comprueba que tu canal esté "
            f"verificado en youtube.com/verify. Detalle: {exc}"
        )
        return False


def add_to_playlist(youtube, playlist_id: str, video_id: str) -> bool:
    """Añade el vídeo a una lista de reproducción; un fallo aquí no debe
    tumbar la subida ya hecha (p. ej. si el ID de la lista es incorrecto o
    no te pertenece)."""
    if not playlist_id:
        return False
    try:
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            },
        ).execute()
        return True
    except HttpError as exc:
        print(f"Aviso: no se pudo añadir el vídeo a la lista de reproducción ({exc}).")
        return False
