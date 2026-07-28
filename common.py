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
