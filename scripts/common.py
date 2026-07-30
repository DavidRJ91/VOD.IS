"""Funciones compartidas entre los pasos del workflow de GitHub Actions."""
from __future__ import annotations

import os
import sys

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


def parse_timestamp_to_seconds(value: str, duration: float) -> float:
    """Convierte 'auto', 'HH:MM:SS', 'MM:SS' o segundos sueltos a segundos,
    recortando al final del vídeo si hace falta. Compartido por la portada
    y por los clips."""
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


def notify_discord(embed: dict) -> None:
    webhook_url = env("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return
    try:
        requests.post(webhook_url, json={"embeds": [embed]}, timeout=10)
    except requests.RequestException:
        # Un aviso fallido nunca debe tumbar el pipeline.
        pass


def die(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)
