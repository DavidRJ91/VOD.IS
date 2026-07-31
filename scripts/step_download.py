"""Paso 1 del workflow: descarga el VOD (Twitch o Kick) — solo vídeo, sin chat."""
from __future__ import annotations

import json
import os
import subprocess
import sys

import yt_dlp

sys.path.insert(0, os.path.dirname(__file__))
from common import detect_platform, die, env, format_for_quality  # noqa: E402

MANIFEST_PATH = "run_data/manifest.json"


def probe_duration_seconds(filepath: str) -> float:
    """Duración real del archivo ya descargado, vía ffprobe. Más fiable que
    el metadato que reporta la plataforma (Kick en particular a veces no
    lo da), y es lo que de verdad importa para repartir los clips."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", filepath],
            capture_output=True, text=True, check=True, timeout=30,
        )
        return float(out.stdout.strip())
    except (subprocess.CalledProcessError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"Aviso: no se pudo calcular la duración real con ffprobe ({exc}).")
        return 0.0


def main() -> None:
    vod_url = env("VOD_URL")
    if not vod_url:
        die("No se recibió VOD_URL.")

    try:
        detect_platform(vod_url)
    except ValueError as exc:
        die(str(exc))

    os.makedirs("run_data", exist_ok=True)
    os.makedirs("downloads", exist_ok=True)

    ydl_opts = {
        "outtmpl": os.path.join("downloads", "%(title)s [%(id)s].%(ext)s"),
        "format": format_for_quality(env("QUALITY", "1080")),
        "merge_output_format": "mp4",
        "restrictfilenames": True,
        "quiet": True,
        "no_warnings": True,
        # Fuera de alcance explícitamente: chat/comentarios/subtítulos.
        "writesubtitles": False,
        "writeautomaticsub": False,
        "writecomments": False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(vod_url, download=True)
            filepath = ydl.prepare_filename(info)
            if not os.path.exists(filepath):
                base, _ = os.path.splitext(filepath)
                candidate = base + ".mp4"
                if os.path.exists(candidate):
                    filepath = candidate
    except yt_dlp.utils.DownloadError as exc:
        die(f"Fallo al descargar el VOD: {exc}")
        return

    if not os.path.exists(filepath):
        die("La descarga terminó pero no se encontró el archivo resultante.")
        return

    reported_duration = info.get("duration") or 0
    real_duration = probe_duration_seconds(filepath)
    duration = real_duration if real_duration > 0 else reported_duration

    manifest = {
        "source_url": vod_url,
        "filepath": filepath,
        "title": info.get("title", "VOD"),
        "description": info.get("description", "") or "",
        "duration": duration,
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False)

    print(f"Descargado: {filepath} (duración: {duration:.0f}s)")


if __name__ == "__main__":
    main()
