"""Funciones compartidas entre los pasos del workflow de GitHub Actions."""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from typing import List, Optional

import requests


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def detect_platform(url: str) -> str:
    lowered = url.lower()
    if "twitch.tv" in lowered:
        return "twitch"
    if "kick.com" in lowered:
        return "kick"
    raise ValueError("La URL no parece ser de Twitch ni de Kick.")


def format_for_quality(quality: str) -> str:
    """Traduce la calidad elegida en la web a un selector de formato de yt-dlp."""
    quality = (quality or "1080").strip().lower()
    if quality in ("best", "maxima", "máxima"):
        return "bestvideo*+bestaudio/best"
    height = "".join(ch for ch in quality if ch.isdigit()) or "1080"
    return f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"


def parse_hhmmss_to_seconds(value: str) -> Optional[float]:
    """Convierte 'HH:MM:SS', 'MM:SS' o segundos sueltos a segundos. None si
    está vacío o no es un formato válido — sin clamping ni valores por
    defecto: eso lo decide quien llama a esta función."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        parts = [float(p) for p in value.split(":")]
    except ValueError:
        return None
    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + part
    return seconds if seconds >= 0 else None


def parse_timestamp_to_seconds(value: str, duration: float) -> float:
    """Convierte 'auto', 'HH:MM:SS', 'MM:SS' o segundos sueltos a segundos,
    recortando al final del vídeo si hace falta. Compartido por la portada
    y por los clips."""
    value = (value or "auto").strip().lower()
    if value == "auto":
        return max((duration or 0) / 2, 0)
    seconds = parse_hhmmss_to_seconds(value)
    if seconds is None:
        return max((duration or 0) / 2, 0)
    if duration:
        seconds = min(seconds, max(duration - 1, 0))
    return max(seconds, 0)


def probe_duration_seconds(filepath: str) -> float:
    """Duración real de un archivo de vídeo, vía ffprobe. Más fiable que el
    metadato que reporta la plataforma (Kick en particular a veces no lo
    da), y es lo que de verdad importa para recortes y clips."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", filepath],
            capture_output=True, text=True, check=True, timeout=30,
        )
        return float(out.stdout.strip())
    except (subprocess.CalledProcessError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"Aviso: no se pudo calcular la duración real con ffprobe ({exc}).")
        return 0.0


def parse_clip_timestamps_list(value: str, duration: float) -> List[float]:
    """Convierte 'HH:MM:SS, MM:SS, 90' en una lista de segundos válidos,
    descartando entradas vacías, negativas o que caen fuera del vídeo."""
    if not value:
        return []
    seconds_list = []
    for chunk in value.split(","):
        seconds = parse_hhmmss_to_seconds(chunk)
        if seconds is None:
            continue
        if duration and seconds >= duration:
            continue
        seconds_list.append(seconds)
    return seconds_list


def notify_discord(embed: dict) -> None:
    webhook_url = env("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return
    try:
        requests.post(webhook_url, json={"embeds": [embed]}, timeout=10)
    except requests.RequestException:
        # Un aviso fallido nunca debe tumbar el pipeline.
        pass


def append_history_entry(entry: dict, max_entries: int = 20) -> bool:
    """Añade una entrada al historial compartido (run_status/history.json),
    con reintento si otra ejecución lo modifica a la vez. Un fallo aquí
    nunca debe tumbar el pipeline: el historial es un plus."""
    token = env("GITHUB_TOKEN")
    repo = env("GITHUB_REPOSITORY")
    branch = env("GITHUB_REF_NAME") or "main"
    if not token or not repo:
        print("Aviso: falta GITHUB_TOKEN o GITHUB_REPOSITORY; no se actualiza el historial.")
        return False

    path = "run_status/history.json"
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    for _ in range(3):
        sha: Optional[str] = None
        history: list = []
        try:
            get_resp = requests.get(url, headers=headers, params={"ref": branch}, timeout=20)
            if get_resp.status_code == 200:
                data = get_resp.json()
                sha = data["sha"]
                history = json.loads(base64.b64decode(data["content"]))
            elif get_resp.status_code != 404:
                get_resp.raise_for_status()
        except (requests.RequestException, ValueError, KeyError) as exc:
            print(f"Aviso: no se pudo leer el historial actual ({exc}).")
            history = []
            sha = None

        history.append(entry)
        history = history[-max_entries:]
        body = {
            "message": "chore: actualizar historial de envíos",
            "content": base64.b64encode(json.dumps(history, ensure_ascii=False).encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        if sha:
            body["sha"] = sha

        try:
            put_resp = requests.put(url, headers=headers, json=body, timeout=20)
            if put_resp.status_code in (200, 201):
                return True
            if put_resp.status_code in (409, 422):
                continue  # alguien más lo modificó a la vez; reintentamos con el sha nuevo
            put_resp.raise_for_status()
        except requests.RequestException as exc:
            print(f"Aviso: no se pudo actualizar el historial ({exc}).")
            return False

    print("Aviso: no se pudo actualizar el historial tras varios intentos (conflictos de escritura).")
    return False


def die(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)
