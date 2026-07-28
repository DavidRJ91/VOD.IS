"""Paso: prepara la miniatura de portada (opcional).

Si THUMBNAIL_URL apunta a una imagen, la descarga. Si no, extrae un
fotograma del propio VOD con ffmpeg en THUMBNAIL_TIMESTAMP (o en la mitad
del vídeo si es "auto"). Cualquier fallo aquí es silencioso a propósito:
la miniatura es un plus — nunca debe tumbar la subida del vídeo.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import requests

sys.path.insert(0, os.path.dirname(__file__))
from common import env  # noqa: E402

MANIFEST_PATH = "run_data/manifest.json"
THUMBNAIL_PATH = "run_data/thumbnail.jpg"
MAX_BYTES = 2 * 1024 * 1024  # límite duro de la API de YouTube para thumbnails.set


def parse_timestamp_to_seconds(value: str, duration: float) -> float:
    value = (value or "auto").strip().lower()
    if value == "auto" or not value:
        return max((duration or 0) / 2, 0)
    try:
        parts = [float(p) for p in value.split(":")]
    except ValueError:
        return max((duration or 0) / 2, 0)
    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + part
    if duration:
        seconds = min(seconds, max(duration - 1, 0))
    return max(seconds, 0)


def try_download_url(url: str) -> bool:
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if not any(t in content_type for t in ("image/jpeg", "image/png", "octet-stream")):
            print(f"Aviso: thumbnail_url no parece una imagen ({content_type}); se omite.")
            return False
        if len(resp.content) > MAX_BYTES:
            print("Aviso: la imagen de portada pesa más de 2MB; se omite.")
            return False
        with open(THUMBNAIL_PATH, "wb") as f:
            f.write(resp.content)
        return True
    except requests.RequestException as exc:
        print(f"Aviso: no se pudo descargar thumbnail_url ({exc}); se omite.")
        return False


def try_extract_frame(video_path: str, timestamp_seconds: float) -> bool:
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", str(timestamp_seconds),
                "-i", video_path,
                "-frames:v", "1",
                "-q:v", "2",
                THUMBNAIL_PATH,
            ],
            check=True,
            capture_output=True,
        )
        return os.path.exists(THUMBNAIL_PATH) and os.path.getsize(THUMBNAIL_PATH) <= MAX_BYTES
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"Aviso: no se pudo extraer el fotograma para la portada ({exc}); se omite.")
        return False


def main() -> None:
    if not os.path.exists(MANIFEST_PATH):
        print("Aviso: no hay manifiesto de descarga; se omite la portada.")
        return
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    ok = False
    thumbnail_url = env("THUMBNAIL_URL")
    if thumbnail_url:
        ok = try_download_url(thumbnail_url)
    if not ok:
        timestamp = parse_timestamp_to_seconds(
            env("THUMBNAIL_TIMESTAMP", "auto"), manifest.get("duration") or 0
        )
        ok = try_extract_frame(manifest["filepath"], timestamp)

    manifest["thumbnail_path"] = THUMBNAIL_PATH if ok else None
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False)

    print("Portada lista." if ok else "Sin portada personalizada; YouTube generará una automática.")


if __name__ == "__main__":
    main()
