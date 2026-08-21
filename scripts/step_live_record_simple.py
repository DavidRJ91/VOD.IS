"""Paso: graba el directo de Twitch de un tirón (desde que se lanza el
envío hasta que el directo termina, o hasta que se acaba el presupuesto de
tiempo de esta ejecución). Al terminar, escribe el mismo manifiesto que
step_download.py, así que el resto del pipeline (portada, subida, clips)
funciona exactamente igual que con un VOD ya terminado.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import die, env  # noqa: E402
from live_capture import capture_live_segment  # noqa: E402

MANIFEST_PATH = "run_data/manifest.json"

# Presupuesto de este paso: el job entero tiene un tope de 340 min en GitHub
# Actions. Dejamos margen para portada + subida (que puede tardar, sobre
# todo con archivos grandes) + clips + notificación.
CAPTURE_BUDGET_SECONDS = 280 * 60


def main() -> None:
    channel_url = env("LIVE_CHANNEL_URL")
    if not channel_url:
        die("No se recibió LIVE_CHANNEL_URL.")
        return
    if "twitch.tv" not in channel_url.lower():
        die("La grabación de directos solo está soportada para Twitch por ahora.")
        return
    if "/videos/" in channel_url.lower() or "/video/" in channel_url.lower():
        die("Esto es un enlace de VOD, no de canal en directo. Usa la URL del canal (twitch.tv/tu_canal).")
        return

    os.makedirs("run_data", exist_ok=True)
    print(f"Grabando el directo (hasta {CAPTURE_BUDGET_SECONDS // 60} minutos, o hasta que termine solo)…")

    result = capture_live_segment(
        channel_url,
        output_dir="downloads",
        max_seconds=CAPTURE_BUDGET_SECONDS,
        from_start=True,
        tag="directo",
    )
    if result is None:
        die("No se pudo capturar nada del directo — comprueba que el canal esté realmente en directo.")
        return

    description = result.description
    if not result.ended_naturally:
        note = (
            "\n\n[Nota: esta grabación se cortó al llegar al tiempo máximo de esta ejecución; "
            "es posible que el directo siguiera en marcha en ese momento.]"
        )
        description = (description or "") + note
        print("Aviso: la grabación se cortó por el límite de tiempo — el directo podría seguir en marcha.")
    else:
        print("El directo terminó de forma natural durante la grabación.")

    manifest = {
        "source_url": channel_url,
        "filepath": result.filepath,
        "title": result.title,
        "description": description,
        "duration": result.duration,
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False)

    print(f"Grabación lista: {result.filepath} (duración: {result.duration:.0f}s)")


if __name__ == "__main__":
    main()
