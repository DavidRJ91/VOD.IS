# VOD2YouTube

Página en GitHub Pages, accesible desde cualquier navegador, que dispara
un workflow de GitHub Actions: descarga un VOD terminado (o graba un
directo mientras está en marcha), opcionalmente lo recorta, lo sube a
YouTube con la portada, título, descripción, visibilidad y lista de
reproducción que elijas, crea clips cortos si quieres, y avisa en
Discord.

## Qué es nuevo en esta versión: grabar directos en marcha

Ahora, además de subir un VOD ya terminado, puedes pegar la URL de tu
canal de Twitch **mientras estás emitiendo** para grabarlo. Hay un
selector arriba del todo con tres modos:

- **VOD terminado** — el modo de siempre: pegas el enlace de un VOD ya
  publicado en Twitch.
- **Directo — todo junto** — graba el directo entero de un tirón y lo
  sube a YouTube **cuando termina** (o al llegar al tope de tiempo de la
  ejecución, lo que pase antes). Sencillo, pero sin protección real
  mientras el directo está en marcha: si algo falla a mitad, se pierde
  todo lo grabado hasta ese momento, porque no hay nada subido a YouTube
  todavía.
- **Directo — por partes** — graba en trozos (tú eliges cuántos minutos
  por parte) y **sube cada uno en cuanto está listo**, mientras sigue
  grabando el siguiente. Esta es la que de verdad te protege: si algo
  falla a mitad, solo pierdes el trozo en curso, no el directo entero. A
  cambio, el resultado en YouTube son varios vídeos separados ("— Parte
  1", "— Parte 2"...), no uno continuo, y hay un pequeño hueco (unos
  segundos) entre el final de una parte y el principio de la siguiente.

### Limitaciones importantes de esta función — léelas antes de confiar en ella

- **Solo Twitch.** Kick no está soportado para grabar directos por
  ahora.
- **Tope de tiempo real.** Cada ejecución de GitHub Actions tiene un
  límite duro de 340 minutos (~5h 40min). En modo "todo junto", si tu
  directo dura más que eso, la grabación se corta ahí — sea como sea, se
  sube lo capturado hasta ese punto, marcado como grabación parcial en
  la descripción. En modo "por partes", simplemente se sube lo que se
  haya llegado a grabar en ese tiempo, cortado por trozos y ya a salvo.
- **No es una retransmisión en directo.** Nada de esto pone tu directo
  "en vivo" en YouTube al mismo tiempo — es una grabación que se sube en
  cuanto está lista (al final del todo, o por trozos según avanza). Si lo
  que buscas es simultanear de verdad como con Restream u otros
  servicios de multistreaming, esto no lo sustituye.
- **No lo he podido probar contra un directo real.
**Antes de confiar en esto para algo importante, haz una prueba corta con un
  directo real y comprueba que el resultado te vale.
- **Portada y clips**: en modo "todo junto" funcionan igual que con un
  VOD normal (se aplican una vez termina la grabación). En modo "por
  partes" no están disponibles — cada parte sale con la portada
  automática que pone YouTube.

## 1. Activa GitHub Pages

**Settings → Pages → Build and deployment → Source: Deploy from a
branch → Branch: `main` / carpeta `/docs`.**

## 2. Tu token

**Actions: Read and write** y **Contents: Read and write**.

## 3. Úsalo

Guarda para ti el enlace con `?config` al final — es el único sitio
donde ves y configuras usuario, repositorio y token. Para el día a día,
el enlace sin `?config` va perfectamente.

Elige el modo arriba del todo, rellena lo que corresponda, y pulsa
**Enviar**. El progreso, la galería de resultados y el historial
funcionan igual sea cual sea el modo que elijas.

## Cómo funciona todo por debajo

**Grabación de directos.** Se usa yt-dlp apuntando al canal (no a un
VOD), con la opción `--hls-use-mpegts` — la recomendada para grabar
directos de forma resistente a cortes. Para terminar una grabación de
forma segura (al llegar al límite de tiempo de un trozo, o de toda la
ejecución), se le manda una señal de interrupción suave (como Ctrl+C),
no un corte brusco, para que el archivo quede en un estado reproducible
aunque el directo siguiera en marcha.

**El resto** — modo oculto de conexión, clips reproducibles/descargables
desde la página, galería de resultados, historial, plantillas, recorte
del VOD, lista de reproducción — funciona exactamente igual que en
versiones anteriores; nada de eso cambió.

## Limitaciones a tener en cuenta

- **Duración máxima por ejecución:** 340 minutos.
- **Disco del runner:** unos 14 GB libres.
- **Portada personalizada:** tu canal debe estar verificado en
  [youtube.com/verify](https://www.youtube.com/verify).
- **Kick** sigue sin API pública estable para detección automática de
  VODs terminados, y su protección anti-bots puede bloquear la descarga
  de forma intermitente — es una limitación del propio Kick/yt-dlp, no
  de este proyecto. La grabación de directos no está soportada para Kick
  en absoluto por ahora.
- Usa esto solo con contenido propio o con permiso explícito del
  creador.
