"""Captura de directos en curso (Twitch). Compartido por los dos modos:
'simple' (todo de una vez) y 'por partes' (varios trozos seguidos).

La captura se interrumpe con SIGINT (como Ctrl+C), no con un corte brusco,
para que yt-dlp cierre el archivo de forma que quede reproducible aunque
el directo siga en marcha. Se usa --hls-use-mpegts, la opción recomendada
para grabar directos de forma resistente a cortes.
"""
from __future__ import annotations

import glob
import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import Optional

GRACE_SECONDS = 30  # tiempo que se le da a yt-dlp para cerrar el archivo tras el SIGINT


@dataclass
class CaptureResult:
    filepath: str
    title: str
    description: str
    duration: float
    ended_naturally: bool  # True = el directo terminó solo; False = se cortó por el límite de tiempo


def is_channel_live(channel_url: str) -> bool:
    """Comprueba si el canal está en directo ahora mismo, sin descargar nada."""
    try:
        out = subprocess.run(
            ["yt-dlp", "--simulate", "--no-warnings", "-j", channel_url],
            capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return False
    if out.returncode != 0:
        return False
    try:
        info = json.loads(out.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return False
    return bool(info.get("is_live"))


def _remux_to_mp4(raw_path: str) -> str:
    """Si el archivo resultante no es ya un mp4 limpio, lo remuxa (copia sin
    recodificar) para que YouTube lo acepte sin problemas."""
    if raw_path.lower().endswith(".mp4"):
        return raw_path
    mp4_path = os.path.splitext(raw_path)[0] + ".mp4"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", raw_path, "-c", "copy", mp4_path],
            check=True, capture_output=True, timeout=600,
        )
        if os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 0:
            os.remove(raw_path)
            return mp4_path
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass
    return raw_path  # si el remux falla, mejor quedarnos con el original que con nada


def capture_live_segment(
    channel_url: str,
    output_dir: str,
    max_seconds: float,
    from_start: bool,
    tag: str,
) -> Optional[CaptureResult]:
    """Graba hasta max_seconds del directo (o hasta que termine solo, lo que
    pase antes). 'tag' debe ser único por llamada (p. ej. 'parte1', 'parte2'
    en modo por partes) para poder encontrar el archivo resultante sin
    confundirlo con el de otra captura anterior. Devuelve None si no se
    pudo capturar nada en absoluto."""
    os.makedirs(output_dir, exist_ok=True)

    out_template = os.path.join(output_dir, f"{tag}-%(title)s.%(ext)s")
    cmd = [
        "yt-dlp",
        "--hls-use-mpegts",
        "--no-part",
        "--restrict-filenames",
        "--quiet", "--no-warnings",
        "--write-info-json",
        "-o", out_template,
    ]
    if from_start:
        cmd.append("--live-from-start")
    cmd.append(channel_url)

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ended_naturally = True
    try:
        proc.wait(timeout=max_seconds)
    except subprocess.TimeoutExpired:
        ended_naturally = False
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    produced = glob.glob(os.path.join(output_dir, f"{tag}-*"))
    video_files = [f for f in produced if os.path.splitext(f)[1] not in (".json", ".part", ".ytdl")]
    if not video_files:
        return None

    # Nos quedamos con el archivo de vídeo más grande (por si quedó algún resto pequeño de más).
    video_path = max(video_files, key=os.path.getsize)
    if os.path.getsize(video_path) == 0:
        return None

    video_path = _remux_to_mp4(video_path)

    title, description = tag, ""
    info_json_candidates = glob.glob(os.path.join(output_dir, f"{tag}-*.info.json"))
    if info_json_candidates:
        try:
            with open(max(info_json_candidates, key=os.path.getctime), encoding="utf-8") as f:
                meta = json.load(f)
            title = meta.get("title") or title
            description = meta.get("description") or description
        except (ValueError, OSError):
            pass

    from common import probe_duration_seconds  # import diferido para evitar ciclos

    duration = probe_duration_seconds(video_path)
    return CaptureResult(
        filepath=video_path,
        title=title,
        description=description,
        duration=duration,
        ended_naturally=ended_naturally,
    )
