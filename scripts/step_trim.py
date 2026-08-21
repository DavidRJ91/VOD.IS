"""Paso: recorta el inicio y/o el final del VOD, si se pidió, antes de que
el resto de pasos (portada, clips, subida) trabajen con él. Si no se pide
ningún recorte, no hace nada — el manifiesto queda tal cual.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import env, parse_hhmmss_to_seconds, probe_duration_seconds  # noqa: E402

MANIFEST_PATH = "run_data/manifest.json"
TRIMMED_PATH = "downloads/vod_trimmed.mp4"


def main() -> None:
    trim_start_raw = env("TRIM_START")
    trim_end_raw = env("TRIM_END")
    if not trim_start_raw and not trim_end_raw:
        print("Sin recorte pedido; se usa el VOD completo.")
        return

    if not os.path.exists(MANIFEST_PATH):
        print("Aviso: no hay manifiesto de descarga; se omite el recorte.")
        return
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    duration = manifest.get("duration") or 0
    start_seconds = parse_hhmmss_to_seconds(trim_start_raw) or 0
    end_seconds = parse_hhmmss_to_seconds(trim_end_raw)
    if end_seconds is None or (duration and end_seconds > duration):
        end_seconds = duration

    if start_seconds <= 0 and (not duration or end_seconds >= duration):
        print("El recorte pedido cubre el vídeo entero; no hace falta tocar nada.")
        return
    if end_seconds <= start_seconds:
        print(
            f"Aviso: el recorte pedido ({start_seconds:.0f}s-{end_seconds:.0f}s) no es válido; "
            "se omite y se sube el VOD completo."
        )
        return

    cmd = ["ffmpeg", "-y"]
    if start_seconds > 0:
        cmd += ["-ss", str(start_seconds)]
    cmd += ["-i", manifest["filepath"]]
    if duration and end_seconds < duration:
        duration_arg = str(max(end_seconds - start_seconds, 0)) if start_seconds > 0 else str(end_seconds)
        cmd += ["-to" if start_seconds == 0 else "-t", duration_arg]
    cmd += ["-c", "copy", TRIMMED_PATH]

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=1800)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"Aviso: no se pudo recortar el VOD ({exc}); se sube el original completo.")
        return

    if not os.path.exists(TRIMMED_PATH):
        print("Aviso: el recorte no produjo un archivo; se sube el original completo.")
        return

    old_filepath = manifest["filepath"]
    manifest["filepath"] = TRIMMED_PATH
    manifest["duration"] = probe_duration_seconds(TRIMMED_PATH) or (end_seconds - start_seconds)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False)

    if os.path.exists(old_filepath):
        os.remove(old_filepath)

    print(f"VOD recortado a {start_seconds:.0f}s-{end_seconds:.0f}s (duración resultante: {manifest['duration']:.0f}s).")


if __name__ == "__main__":
    main()
