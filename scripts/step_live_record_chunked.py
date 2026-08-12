"""Paso: graba el directo de Twitch EN TROZOS, subiendo cada uno a YouTube
en cuanto está listo, hasta que el directo termina o se agota el
presupuesto de tiempo de esta ejecución. A diferencia del modo simple,
aquí sí hay protección real durante el directo: si algo falla a mitad,
solo se pierde el trozo en curso, no todo lo grabado hasta ese momento.

Hace todo el trabajo internamente (a diferencia del resto del pipeline,
que va paso a paso): comprobar si sigue en directo, grabar, subir,
avisar por Discord, y repetir.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(__file__))
from common import append_history_entry, die, env, notify_discord  # noqa: E402
from live_capture import is_channel_live, capture_live_segment  # noqa: E402
from youtube_common import YouTubeError, get_authenticated_service, upload_video  # noqa: E402

JOB_BUDGET_SECONDS = 320 * 60  # deja margen frente al tope de 340 min del job entero
MIN_USEFUL_CHUNK_SECONDS = 120  # no merece la pena arrancar un trozo nuevo con menos que esto
DEFAULT_CHUNK_MINUTES = 25
MIN_CHUNK_MINUTES = 5
MAX_CHUNK_MINUTES = 60


def resolve_chunk_seconds() -> int:
    try:
        minutes = int(env("CHUNK_MINUTES", str(DEFAULT_CHUNK_MINUTES)) or DEFAULT_CHUNK_MINUTES)
    except ValueError:
        minutes = DEFAULT_CHUNK_MINUTES
    minutes = max(MIN_CHUNK_MINUTES, min(MAX_CHUNK_MINUTES, minutes))
    return minutes * 60


def validate_channel_url(channel_url: str) -> None:
    if not channel_url:
        die("No se recibió LIVE_CHANNEL_URL.")
    if "twitch.tv" not in channel_url.lower():
        die("La grabación de directos solo está soportada para Twitch por ahora.")
    if "/videos/" in channel_url.lower() or "/video/" in channel_url.lower():
        die("Esto es un enlace de VOD, no de canal en directo. Usa la URL del canal (twitch.tv/tu_canal).")


def publish_live_parts_result(parts: list[dict]) -> None:
    """Publica el resultado en run_status/<id>.json, igual que
    step_publish_result.py, para que la galería de la web también pueda
    mostrar las partes de un directo grabado por trozos."""
    token = env("GITHUB_TOKEN")
    repo = env("GITHUB_REPOSITORY")
    run_id = env("GITHUB_RUN_ID")
    branch = env("GITHUB_REF_NAME") or "main"
    if not token or not repo or not run_id:
        print("Aviso: falta GITHUB_TOKEN, GITHUB_REPOSITORY o GITHUB_RUN_ID; no se publica el resultado.")
        return

    payload = {"main": None, "clips": [], "live_parts": parts}
    path = f"run_status/{run_id}.json"
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    content_b64 = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")
    try:
        resp = requests.put(
            url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            json={"message": f"chore: publicar resultado ({run_id})", "content": content_b64, "branch": branch},
            timeout=20,
        )
        resp.raise_for_status()
        print(f"Resultado publicado en {path}.")
    except requests.RequestException as exc:
        print(f"Aviso: no se pudo publicar el resultado ({exc}).")


def main() -> None:
    channel_url = env("LIVE_CHANNEL_URL")
    validate_channel_url(channel_url)

    chunk_seconds = resolve_chunk_seconds()
    base_title = env("VIDEO_TITLE") or ""
    base_description = env("VIDEO_DESCRIPTION") or ""
    privacy = env("PRIVACY", "unlisted")
    scheduled_at = env("SCHEDULED_AT")
    category_id = env("YOUTUBE_CATEGORY_ID") or "20"

    if not is_channel_live(channel_url):
        die("El canal no parece estar en directo ahora mismo.")
        return

    try:
        youtube = get_authenticated_service()
    except YouTubeError as exc:
        die(f"No se pudo conectar con YouTube antes de empezar a grabar: {exc}")
        return

    os.makedirs("downloads", exist_ok=True)
    parts: list[dict] = []
    start_time = time.monotonic()
    part_num = 0
    first_chunk = True
    stream_ended = False

    while True:
        elapsed = time.monotonic() - start_time
        remaining = JOB_BUDGET_SECONDS - elapsed
        if remaining < MIN_USEFUL_CHUNK_SECONDS:
            print("Presupuesto de tiempo de esta ejecución agotado; se termina aquí.")
            break

        if not first_chunk and not is_channel_live(channel_url):
            print("El directo ya ha terminado.")
            stream_ended = True
            break

        part_num += 1
        this_chunk_max = min(chunk_seconds, remaining)
        print(f"Grabando parte {part_num} (hasta {this_chunk_max / 60:.0f} min)…")

        result = capture_live_segment(
            channel_url,
            output_dir="downloads",
            max_seconds=this_chunk_max,
            from_start=first_chunk,
            tag=f"parte{part_num}",
        )
        first_chunk = False

        if result is None:
            print(f"Aviso: no se pudo capturar la parte {part_num}.")
            if not is_channel_live(channel_url):
                stream_ended = True
                break
            continue

        title = f"{base_title or result.title} — Parte {part_num}"[:100]
        try:
            video_id = upload_video(
                youtube,
                filepath=result.filepath,
                title=title,
                description=base_description or result.description,
                tags=[],
                category_id=category_id,
                privacy=privacy,
                scheduled_at=scheduled_at,
            )
            video_url = f"https://youtu.be/{video_id}"
            parts.append({
                "video_id": video_id,
                "video_url": video_url,
                "part_number": part_num,
                "ended_naturally": result.ended_naturally,
            })
            print(f"Parte {part_num} subida: {video_url}")
            notify_discord({
                "title": f"Parte {part_num} subida",
                "description": f"**{title}**",
                "color": 0x1D9E75,
                "fields": [{"name": "YouTube", "value": video_url, "inline": False}],
            })
        except YouTubeError as exc:
            print(f"Aviso: no se pudo subir la parte {part_num} ({exc}).")
            notify_discord({
                "title": f"Fallo al subir la parte {part_num}",
                "description": f"**{title}**",
                "color": 0xE24B4A,
                "fields": [{"name": "Error", "value": str(exc)[:1000], "inline": False}],
            })
        finally:
            if os.path.exists(result.filepath):
                os.remove(result.filepath)

        if result.ended_naturally:
            print("El directo terminó de forma natural durante esta parte.")
            stream_ended = True
            break

    publish_live_parts_result(parts)

    summary_color = 0x1D9E75 if parts else 0xE24B4A
    summary_note = "El directo terminó." if stream_ended else "Se cortó por el límite de tiempo de esta ejecución; el directo podría seguir en marcha."
    notify_discord({
        "title": f"Grabación por partes terminada — {len(parts)} parte(s)",
        "description": f"**{base_title or channel_url}**\n{summary_note}",
        "color": summary_color,
        "fields": [
            {"name": f"Parte {p['part_number']}", "value": p["video_url"], "inline": False} for p in parts
        ] or [{"name": "Resultado", "value": "No se pudo subir ninguna parte.", "inline": False}],
    })

    append_history_entry({
        "run_id": env("GITHUB_RUN_ID"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "outcome": "success" if parts else "failure",
        "vod_url": channel_url,
        "title": base_title or channel_url,
        "clip_count": 0,
        "live_parts_count": len(parts),
    })

    if not parts:
        die("No se pudo subir ninguna parte del directo.")


if __name__ == "__main__":
    main()
