# VOD2YouTube

Página en GitHub Pages, accesible desde cualquier navegador, que dispara
un workflow de GitHub Actions: descarga el VOD (Twitch o Kick, solo
vídeo, sin chat), opcionalmente lo recorta, lo sube a YouTube con la
portada, título, descripción, visibilidad y lista de reproducción que
elijas, crea clips cortos si quieres, y avisa en Discord.

## Qué es nuevo en esta versión

- **Recortar el vídeo principal.** Indica desde/hasta qué instante subir
  (para saltarte el rato muerto antes de empezar, o cortar al final). La
  portada y los clips se calculan ya sobre el vídeo recortado.
- **Clips con marcas de tiempo manuales.** Además del reparto automático,
  puedes pegar instantes concretos ("5:30, 12:45, 47:10") si ya sabes qué
  momentos quieres — tiene prioridad sobre el número de clips.
- **Duración de clip configurable**: 15, 30 o 60 segundos.
- **Añadir a una lista de reproducción de YouTube** automáticamente,
  dando su ID.
- **Plantillas de título/descripción.** Guarda el título y la
  descripción actuales en este navegador, y cárgalos de un clic la
  próxima vez.
- **Botón "Rellenar con el último envío"**, para reintentar rápido si
  algo falló, o para partir de lo último que enviaste.
- **Historial de envíos** directamente en la página, con enlace a cada
  vídeo y si terminó bien o mal — sin ir a la pestaña Actions de GitHub.

## 1. Sube este proyecto a GitHub

Si ya tenías una versión anterior en tu repositorio: reemplaza estos
archivos por los de este zip —

- **Nuevo:** `scripts/step_trim.py`.
- **Cambia:** `scripts/common.py`, `scripts/step_clips.py`,
  `scripts/step_notify.py`, `scripts/step_upload.py`,
  `scripts/youtube_common.py`, `.github/workflows/process-vod.yml`,
  `docs/index.html`, `docs/style.css`, `docs/app.js`. Más seguro abrir
  cada uno en GitHub, borrar su contenido y pegar el nuevo, que editar a
  mano.
- `scripts/step_download.py`, `scripts/step_thumbnail.py`,
  `scripts/step_publish_result.py`, `scripts/get_refresh_token.py`,
  `requirements.txt` no cambian si ya los tenías de una ronda anterior.
- Todo lo demás (tus 4 secretos de YouTube/Discord, el token, Pages)
  sigue exactamente igual — no hay permisos nuevos que configurar.

## 2. Activa GitHub Pages (si no lo hiciste ya)

**Settings → Pages → Build and deployment → Source: Deploy from a
branch → Branch: `main` / carpeta `/docs`.**

## 3. Tu token

Necesita permisos de **Actions: Read and write** y **Contents: Read and
write** sobre el repositorio. Si ya lo tenías configurado de una ronda
anterior, no hace falta tocar nada — no hay permisos nuevos en esta
versión.

## 4. Úsalo

Guarda para ti el enlace con `?config` al final (por ejemplo:
`https://tu-usuario.github.io/tu-repo/?config`) — es el único sitio
donde ves y configuras usuario, repositorio y token; nadie que abra el
enlace normal ve nada de eso. Para el día a día, el enlace sin `?config`
va perfectamente — la página recuerda tu token en ese navegador.

Pega el VOD, ajusta lo que quieras (recorte, portada, visibilidad,
lista de reproducción, clips), y pulsa **Enviar VOD**. Verás el progreso
en tiempo real, y al terminar, la galería con el vídeo y los clips, más
la entrada correspondiente en el historial de abajo.

## Cómo funciona todo por debajo

**El panel de conexión con GitHub** sigue existiendo en el código de la
página (ningún sitio 100% estático puede ocultar código fuente del
todo), pero no se renderiza visible salvo con `?config` en la URL. Si
algún día quieres que **otra persona** (un mod, un editor) pueda enviar
VODs de verdad, su propio navegador necesita un token válido — no hay
forma de evitarlo sin montar un servidor propio. Dale un token aparte
con permisos mínimos (solo Actions, sin Contents), nunca el tuyo.

**Los clips** no se suben a YouTube: se publican temporalmente en tu
repositorio (`clip_output/<id-de-la-ejecución>/clip-N.mp4`). En la
galería, cada uno tiene un botón "Cargar y reproducir" que trae el
contenido real, lo reproduce ahí mismo, ofrece un enlace de descarga
(reutilizando lo ya cargado, sin traerlo dos veces), y borra el archivo
del repositorio en cuanto se carga. Si generas clips y cierras la
pestaña sin cargarlos, se quedan en `clip_output/` hasta que entres a
por ellos a mano — no pasa nada grave, son pocos MB.

**La galería de resultados** viene de un archivo pequeño
(`run_status/<id-de-la-ejecución>.json`) que el workflow escribe al
terminar y la página borra en cuanto lo lee.

**El historial**, en cambio, se guarda en `run_status/history.json` y
**no se borra**: cada envío (éxito o fallo) añade una entrada, guardando
como mucho las últimas 20. Si dos ejecuciones terminan casi a la vez, el
sistema reintenta la escritura para no perder ninguna.

**"Rellenar con el último envío"** guarda los datos del formulario en tu
navegador (no en GitHub) cada vez que envías algo. Limitación honesta:
si habías elegido "Subir imagen" para la portada, el archivo en sí no se
puede recordar (no cabe de forma razonable en el navegador) — al
reintentar, esa opción vuelve a "Automática".

## Limitaciones a tener en cuenta

- **Duración máxima por ejecución:** 340 minutos. Con clips o recortes
  añadidos, el proceso tarda algo más — si te acercas al límite, baja la
  calidad o reduce el número de clips.
- **Disco del runner:** unos 14 GB libres.
- **Portada y lista de reproducción personalizadas:** tu canal debe
  estar verificado en [youtube.com/verify](https://www.youtube.com/verify)
  para la portada; para la lista, el ID debe ser tuyo o de una lista
  donde tengas permiso de edición.
- **Kick** sigue sin API pública estable para detección automática, y su
  protección anti-bots puede bloquear la descarga de forma intermitente
  — es una limitación del propio Kick/yt-dlp, no de este proyecto.
- Usa esto solo con contenido propio o con permiso explícito del
  creador.
