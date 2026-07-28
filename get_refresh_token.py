"""Ejecútalo UNA VEZ, en tu propio ordenador (no en GitHub Actions).

Abre el navegador para iniciar sesión en YouTube y, al final, imprime los tres
valores que debes guardar como secretos del repositorio en GitHub.

Requisitos:
    pip install google-auth-oauthlib

Necesitas, en esta misma carpeta, tu `client_secret.json` descargado de
Google Cloud Console (credencial OAuth de tipo "Aplicación de escritorio",
con la API de YouTube Data v3 habilitada).
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(port=0)

print("\nGuarda estos tres valores como secretos del repositorio en GitHub:")
print("(Settings → Secrets and variables → Actions → New repository secret)\n")
print(f"YOUTUBE_CLIENT_ID = {creds.client_id}")
print(f"YOUTUBE_CLIENT_SECRET = {creds.client_secret}")
print(f"YOUTUBE_REFRESH_TOKEN = {creds.refresh_token}")
