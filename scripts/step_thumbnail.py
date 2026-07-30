"""Paso: prepara la miniatura de portada (opcional).

Hay tres fuentes posibles, en este orden de prioridad:
1. THUMBNAIL_REPO_PATH — una imagen subida por la web al propio repositorio;
   se lee con la API de GitHub (autenticada, funciona en repos privados).
2. THUMBNAIL_URL — una URL externa directa a una imagen.
3. Si ninguna de las dos aplica o falla, se extrae un fotograma del propio
   VOD con ffmpeg en THUMBNAIL_TIMESTAMP (o en la mitad del vídeo si es
   "auto"). Cualquier fallo aquí es silencioso a propósito: la miniatura es
   un plus — nunca debe tumbar la subida del vídeo.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys

import requests

sys.path.insert(0, os.path.dirname(__file__))
from common import env, parse_timestamp_to_seconds  # noqa: E402

MANIFEST_PATH = "run_data/manifest.json"
THUMBNAIL_PATH = "run_data/thumbnail.jpg"
MAX_BYTES = 2 * 1024 * 1024  # límite duro de la API de YouTube para thumbnails.set


def try_read_from_repo(path: str) -> bool:
    """Lee una imagen subida por la web al propio repo, vía la API autenticada
    (a diferencia de una URL de raw.githubusercontent.com, esto funciona
    igual en repos públicos y privados)."""
    token = env("GITHUB_TOKEN")
    repo = env("GITHUB_REPOSITORY")
    if not token or not repo:
        print("Aviso: falta GITHUB_TOKEN o GITHUB_REPOSITORY; se omite la miniatura subida.")
        return False
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    try:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("encoding") != "base64":
            print("Aviso: formato inesperado al leer la miniatura del repo; se omite.")
            return False
        raw = base64.b64decode(data["content"])
        if len(raw) > MAX_BYTES:
            print("Aviso: la miniatura subida pesa más de 2MB; se omite.")
            return False
        with open(THUMBNAIL_PATH, "wb") as f:
            f.write(raw)
        return True
    except requests.RequestException as exc:
        print(f"Aviso: no se pudo leer la miniatura subida al repo ({exc}); se omite.")
        return False


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
    repo_path = env("THUMBNAIL_REPO_PATH")
    thumbnail_url = env("THUMBNAIL_URL")
    if repo_path:
        ok = try_read_from_repo(repo_path)
    elif thumbnail_url:
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
