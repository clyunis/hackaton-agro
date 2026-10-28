# Manifest de fuentes descargadas

Registro de trazabilidad para el sistema de citación del asistente (Desafío 4).
Fuente de la lista: `raw_data/fuentes.txt`. Fecha de descarga: 2026-10-28.
Método: `curl -L` con User-Agent de navegador (Chrome 129 / Windows), timeout 30s, un reintento
con headers adicionales (`Accept-Language`) ante fallo de conexión.

| Línea | URL original | Archivo guardado | Content-Type obtenido | Fecha descarga | Notas |
|---|---|---|---|---|---|
| 1 | https://www.argentina.gob.ar/senasa/programas-sanitarios/productosveterinarios-fitosanitarios-y-fertilizantes/registro-nacional-de-terapeutica-vegetal | 01-senasa-registro-terapeutica-vegetal.html | text/html (HTTP 200) | 2026-10-28 | Página informativa estática, OK |
| 3 | https://aps2.senasa.gov.ar/vademecum/app/publico | **no guardado** — portal JS-only | text/html (HTTP 200), pero cuerpo es solo el shell SPA (`<div id="root">` vacío + `bundle.js`) | 2026-10-28 | Requiere ejecución de JS para mostrar el vademecum real; descargar el HTML no aporta contenido. Omitido. |
| 5 | https://www.argentina.gob.ar/inta/redes-de-laboratorios-inta/laboratorio-de-suelo-y-material-vegetal-grupo-relacion-suelo-cultivo-eea-balcarce | 05-inta-laboratorio-suelo-balcarce.html | text/html (HTTP 200) | 2026-10-28 | OK |
| 7 | https://cultivaresargentinos.com/maiz/ | 07-cultivaresargentinos-maiz.html | text/html (HTTP 200) | 2026-10-28 | OK |
| 9 | https://www.recsoargentina.com/ | 09-recsoargentina-home.html | text/html (HTTP 200) | 2026-10-28 | OK, página de inicio (1.1 MB, incluye assets inline referenciados) |
| 11 | https://aapresid.org.ar/rem | 11-aapresid-rem.html | text/html (HTTP 200) | 2026-10-28 | OK |
| 13 | https://www.aapresid.org.ar/es/novedades/68d1ba18379fe5caf64926fd | 13-aapresid-novedad-68d1ba18.html | text/html (HTTP 200) | 2026-10-28 | OK |
| 15 | https://www.argentina.gob.ar/node/424701 | 15-argentina-gob-node-424701.html | text/html (HTTP 200) | 2026-10-28 | OK |
| 17 | https://www.argentina.gob.ar/normativa | **no guardado** — portal de búsqueda | text/html (HTTP 200), pero el cuerpo es el "Buscador de normativa": solo formularios POST de búsqueda (`apachesolr-search-custom-page-search-form`, `infoleg-normativa-search-form`, `argobar-consulta-infoleg-consulta-avanzada`) y enlaces de navegación, sin contenido normativo propio | 2026-10-28 | Requiere interacción (búsqueda) para mostrar normas reales; es un portal de consulta, no un documento. Omitido. |
| 19 | https://normas.gba.gob.ar/ar-b/ley/1988/10699/6118 | 19-gba-ley-10699-1988.html | text/html (HTTP 200) | 2026-10-28 | OK, texto de la ley |
| 21 | https://normas.gba.gob.ar/ar-b/decreto/1991/499/99285 | 21-gba-decreto-499-1991.html | text/html (HTTP 200) | 2026-10-28 | OK, texto del decreto |
| 23 | https://sibom.slyt.gba.gob.ar/bulletins/6329/contents/1655984 | 23-sibom-bulletin-6329.html | text/html (HTTP 200) | 2026-10-28 | OK |
| 25 | https://sibom.slyt.gba.gob.ar/bulletins/7071/contents/1724346 | 25-sibom-bulletin-7071.html | text/html (HTTP 200) | 2026-10-28 | OK |
| 27 | https://sibom.slyt.gba.gob.ar/bulletins/7071/contents/1724346 | 27-sibom-bulletin-7071-dup.html | text/html (HTTP 200) | 2026-10-28 | URL idéntica a la línea 25 (duplicado en fuentes.txt); se guardó de todas formas para mantener la indexación 1:1 con el número de línea. Mismo contenido que el archivo 25. |
| 29 | https://sibom.slyt.gba.gob.ar/bulletins/14417/contents/2347976 | 29-sibom-bulletin-14417.html | text/html (HTTP 200) | 2026-10-28 | OK |
| 31 | https://www.argentina.gob.ar/inta/informacion-agroclimatica/heladas | 31-inta-agroclimatica-heladas.html | text/html (HTTP 200) | 2026-10-28 | OK |
| 33 | https://www.argentina.gob.ar/inta/tecnologias/sistema-de-monitoreo-remoto-de-pulverizaciones-y-su-deriva | 33-inta-monitoreo-pulverizaciones-deriva.html | text/html (HTTP 200) | 2026-10-28 | OK |
| 35 | https://cac.bcr.com.ar/es/precios-de-pizarra/consultas | **no guardado** — portal de consulta | text/html (HTTP 200), pero el cuerpo es un formulario GET de consulta de precios (`cms-tweaks-query-form`, action `/es/precios-de-pizarra/consultas`) sin tabla de precios cargada | 2026-10-28 | Requiere enviar parámetros de búsqueda para obtener los precios de pizarra reales; es una herramienta de consulta, no un documento estático. Omitido. |
| 37 | https://bcp.org.ar/index.asp | 37-bcp-index.html | text/html (HTTP 200) | 2026-10-28 | OK, home de Bolsa de Cereales y Productos de Bahía Blanca |
| 39 | https://www.facma.com.ar/index.html | 39-facma-index.html | text/html (HTTP 200) | 2026-10-28 | OK |
| 41 | https://agrocontratistas.com.ar/pdf/LABORES_202610_1.pdf | 41-agrocontratistas-labores-202610.pdf | application/pdf (HTTP 200) | 2026-10-28 | OK, PDF descargado directo, verificado con `file` (PDF 1.4, 1 página) |
| 43 | https://fatrac.org.ar/tarifas/ | 43-fatrac-tarifas.html | text/html (HTTP 200) | 2026-10-28 | OK |
| 45 | https://www.casafe.org/ | 45-casafe-home.html | text/html (HTTP 200) | 2026-10-28 | OK |
| 47 | https://crea.org.ar/ | 47-crea-home.html | text/html (HTTP 200) | 2026-10-28 | OK |
| 49 | https://www.smn.gob.ar/ | **no guardado** — bloqueado | HTTP 403, `cf-mitigated: challenge` (Cloudflare bot-challenge) | 2026-10-28 | Fallido. Primer intento con UA de Chrome de escritorio -> 403. Reintento con headers adicionales (`Accept`, `Accept-Language`, `Referer`) -> 403 de nuevo. El sitio exige resolver un challenge de Cloudflare (JS/Turnstile) que no se puede superar con curl. Registrado como fallo. |
| 51 | https://repositorio.inta.gob.ar/handle/20.500.12123/22378 | 51-repositorio-inta-handle-22378.html | text/html (HTTP 200) | 2026-10-28 | OK. Es la página del ítem en el repositorio (DSpace); el PDF del documento en sí no se descargó porque la URL dada es la página del ítem, no el enlace directo al PDF — si se necesita el PDF, habría que seguir el enlace de descarga dentro de esta página en una pasada futura. |

## Resumen

- **URLs no vacías en fuentes.txt:** 26 (líneas 1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31,33,35,37,39,41,43,45,47,49,51). La línea 27 es un duplicado exacto de la línea 25.
- **Guardadas como documento real:** 21 (20 HTML + 1 PDF).
- **Omitidas por ser portal de búsqueda/consulta sin contenido estático (JS o formulario):** 3 — líneas 3 (vademecum SENASA, SPA), 17 (buscador de normativa Argentina.gob.ar), 35 (consulta de precios de pizarra BCR).
- **Fallidas (error de descarga):** 1 — línea 49 (smn.gob.ar, bloqueado por challenge de Cloudflare, HTTP 403 en dos intentos).
