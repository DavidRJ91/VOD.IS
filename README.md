# VOD2YouTube (versión web, sin página propia)

Descarga un VOD de Twitch (solo vídeo, sin chat), lo sube a YouTube
con la portada, título, descripción y visibilidad que elijas, y avisa en
Discord. Todo corre en GitHub Actions — no instalas nada en tu ordenador
para usarlo, y lo arrancas desde cualquier navegador, en cualquier parte
del mundo, con tu cuenta normal de GitHub.

## Por qué no hay una página propia

La primera versión de esto incluía una página en GitHub Pages con un
formulario a medida. Funcionaba, pero exigía activar Pages, crear un token
de acceso personal y pegarlo en el navegador — pasos extra que no aportan
nada que GitHub no te dé ya gratis.

**GitHub genera automáticamente un formulario** para cualquier workflow
que acepte parámetros (`workflow_dispatch`), visible en la pestaña
**Actions** de tu repositorio. Es lo que vas a usar: sin instalar nada,
sin tokens que gestionar, funciona igual desde el móvil que desde un
ordenador, en cualquier navegador donde tengas sesión iniciada en GitHub.

## 1. Sube este proyecto a GitHub

Crea un repositorio y sube este contenido tal cual. A diferencia de la
versión con Pages, **puede ser privado** si prefieres que el código no sea
público (GitHub Actions es gratis igualmente; en repos privados el plan
gratuito da 2.000 minutos al mes, de sobra para uso personal — en público
es ilimitado).

## 2. Configura YouTube (una sola vez)

GitHub Actions no tiene navegador, así que la autenticación no puede ser
un login interactivo cada vez: se genera un *refresh token* una sola vez.
Dos formas de conseguirlo — elige la que te resulte más cómoda:

### Opción A — Sin instalar nada (recomendada)

1. En [Google Cloud Console](https://console.cloud.google.com/): crea un
   proyecto, habilita **YouTube Data API v3**, configura la pantalla de
   consentimiento OAuth (tipo "Externa", añádete como usuario de prueba) y
   crea una credencial OAuth de tipo **Aplicación web** con
   `https://developers.google.com/oauthplayground` como URI de
   redirección autorizada. Copia el Client ID y el Client Secret.
2. Ve a [Google OAuth Playground](https://developers.google.com/oauthplayground/),
   pulsa el icono de engranaje (arriba a la derecha), marca **"Use your
   own OAuth credentials"** y pega tu Client ID y Client Secret.
3. En el panel izquierdo, busca **YouTube Data API v3**, marca el scope
   `.../auth/youtube.upload` y pulsa **Authorize APIs**. Inicia sesión con
   la cuenta de YouTube donde quieres publicar.
4. Pulsa **Exchange authorization code for tokens**. Copia el `Refresh
   token` que aparece.

### Opción B — Con un script local

```bash
pip install google-auth-oauthlib
python scripts/get_refresh_token.py
```
(con tu `client_secret.json` de tipo "Aplicación de escritorio" en la
misma carpeta). Imprime los tres valores en la terminal.

## 3. Guarda los secretos en el repositorio

**Settings → Secrets and variables → Actions → New repository secret**:

| Nombre | Valor |
|---|---|
| `YOUTUBE_CLIENT_ID` | el Client ID de Google Cloud Console |
| `YOUTUBE_CLIENT_SECRET` | el Client Secret de Google Cloud Console |
| `YOUTUBE_REFRESH_TOKEN` | el refresh token obtenido en el paso 2 |
| `DISCORD_WEBHOOK_URL` | tu webhook (Config. del servidor → Integraciones → Webhooks) |

Opcional, en la pestaña **Variables** (no Secrets, no es sensible):

| Nombre | Valor |
|---|---|
| `YOUTUBE_CATEGORY_ID` | si no lo defines, usa 20 (Videojuegos) |

## 4. Úsalo

En tu repositorio: **Actions → Procesar VOD → Run workflow**. Rellena:

- **vod_url** — el enlace del VOD (obligatorio).
- **title** / **description** — vacíos = se usan los originales del VOD.
- **privacy** — `public`, `unlisted` u `scheduled`.
- **scheduled_at** — si privacy es `scheduled`, fecha/hora UTC en formato
  `AAAA-MM-DDTHH:MM:SSZ`.
- **quality** — `720`, `1080` o `best`.
- **thumbnail_url** — enlace directo a una imagen JPG/PNG de máx. 2MB para
  la portada. Vacío = se extrae automáticamente un fotograma del propio
  VOD.
- **thumbnail_timestamp** — si no das una URL, el instante del VOD del
  que sacar la portada (`HH:MM:SS`), o `auto` para el punto medio.

Pulsa **Run workflow** y ya está. Puedes seguir el progreso ahí mismo, en
la propia pantalla de GitHub, o simplemente cerrarla — Discord te avisa
igual cuando termine.

## Sobre la portada personalizada

- **Tu canal debe estar verificado** en
  [youtube.com/verify](https://www.youtube.com/verify) para poder poner
  portadas personalizadas; si no lo está, el vídeo se sube igual, solo que
  sin portada personalizada (YouTube genera una automática), y verás un
  aviso en el registro del workflow.
- Si `thumbnail_url` falla (enlace roto, pesa de más, no es una imagen),
  el sistema no aborta: cae automáticamente a extraer un fotograma del
  VOD, así que casi siempre acabas con alguna portada propia.

## Limitaciones a tener en cuenta

- **Duración máxima por ejecución:** 340 minutos (el límite de
  GitHub Actions son 360). Si te acercas, baja la calidad a 720p/1080p.
- **Disco del runner:** unos 14 GB libres — de sobra para la mayoría de
  VODs en 1080p.
  
**- Usa esto solo con contenido propio o con permiso explícito del
  creador: redistribuir VODs ajenos puede infringir los términos de
  Twitch y derechos de autor.**
