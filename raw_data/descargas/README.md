# Descargas desde `raw_data/fuentes.txt`

Generado el 28/10/2026. Para cada URL listada en `raw_data/fuentes.txt` se visitó la página
y se descargaron los **archivos reales** (PDF/XLS/XLSX/DOC/DOCX/ODS/ZIP) enlazados dentro de
ella — no el HTML de la página en sí — siguiendo como guía los puntos R01–R27 de
`documentation/04 - Asistente agronómico.pdf`.

No se incluye `fuentes.txt` línea a línea 1:1 porque varias páginas no tienen un "archivo"
descargable (son buscadores/apps) — eso se documenta abajo en "No descargable".

## Carpetas

- `01_senasa_rntv/` — SENASA, Registro Nacional de Terapéutica Vegetal (R01).
  Formularios de inscripción, LMR, listados de autorizaciones (cultivos menores, VANTs,
  langostas/tucuras), resoluciones de prohibición de principios activos (clorpirifós,
  fipronil, 2,4-D ésteres, carbofuran y otros — Res. 32/19 y modificatorias), zonas
  agroecológicas, procedimiento de ampliación de uso, gestión de envases, planta
  elaboradoras. Útil para C01, C02, C03, C11, C17.
- `02_inta_pulverizaciones/` — INTA, ficha técnica (inglés) del sistema de monitoreo remoto
  de pulverizaciones y deriva (R19 / C17).
- `03_normativa_provincial/` — Ley 10.699/1988 (PDF original) y Decreto 499/1991
  (texto actualizado HTML, ver nota) de la Provincia de Buenos Aires (R12–R13), más el
  texto completo de la Ordenanza 17.404/2021 de Tandil, su Decreto reglamentario 1800/2022
  y el Decreto 423/2026 que suspende transitoriamente el art. 8 (R14–R16 / C10).
- `04_maiz_ensayos/` — Red de ensayos comparativos de maíz del sur de la provincia de
  Buenos Aires, campaña 2024/25: rendimientos relativos (xlsx), análisis de estabilidad
  multiambiental (pdf) y el paquete completo por localidad (zip) (R06 / C05, C18).
- `05_recso_soja/` — Informe RECSO (Red Nacional de Evaluación de Cultivares de Soja),
  campaña 2025/26 (R07 / C05, C18). Archivo pesado (~89 MB, 456 páginas).
- `06_girasol_inta/` — Red Nacional de Cultivares de Girasol 2024/25, INTA Balcarce:
  informes finales Buenos Aires Norte y Buenos Aires Sur/La Pampa (xlsx) (R27 / C05).
- `07_bcp_bahia_blanca/` — Bolsa de Cereales y Productos de Bahía Blanca: movimiento
  portuario (septiembre 2026) e informe USDA (octubre 2026) (R21 / C12).
- `08_facma_precios_labores/` — FACMA, precios orientativos de servicios agrícolas:
  labores y siembra, aplicaciones (líquidos/sólidos), henificación, embolsado/extracción,
  y cosecha por cultivo (soja, sorgo, girasol, maíz, trigo/avena/cebada, lino/colza/alpiste)
  (R22 / C14). Nota: `fuentes.txt` línea 41 ya apuntaba directo a uno de estos PDFs.
- `09_fatrac_tarifas/` — FATRAC, tarifas de flete: cereales y espigas en PBA (enero y abril
  2026) y tarifa nacional/cereales históricas (2024) (R23 / C15).
- `10_casafe_publicaciones/` — CASAFE, documentos técnicos: drones, agricultura
  regenerativa, áreas circundantes a sitios poblados, BPA de aplicación, manuales de
  depósito/transporte/emergencias, clasificación toxicológica, glifosato (IARC/EFSA), etc.
  (R24 / contexto complementario para C02, C03, C17).
- `11_casafe_guia_marbetes/` — **Marbetes/monografías de productos fitosanitarios**,
  scrapeados de la "Guía de Productos Fitosanitarios" online de CASAFE
  (`guiaonline.casafe.org/documentos/<id>.pdf`). El buscador web de la guía exige
  registro, pero el endpoint de PDF por documento es público y no requiere login
  (verificado con `curl`, sin cookies/sesión). Se escaneó todo el rango de IDs
  (1–1066) y se descargaron los **746 documentos válidos** encontrados — es la base
  completa publicada por CASAFE, no solo una muestra. Cada PDF trae, por principio
  activo (o combinación), marcas comerciales, dosis por cultivo/plaga/maleza, momento
  de aplicación, período de carencia, toxicología, EPP, riesgos ambientales y el
  registro SENASA de cada marca (N° inscripción, formulación, concentración, clase
  toxicológica) — contenido equivalente al del marbete oficial, aunque compilado por
  CASAFE "al solo efecto enunciativo" (ver disclaimer en `guiaonline.casafe.org/`;
  para el marbete legal vigente de una marca puntual, la fuente primaria sigue siendo
  el vademécum de SENASA, R02). `catalogo_marbetes.csv` indexa los 746 archivos (id,
  archivo, título, marcas comerciales, uso/tipo, cultivos detectados en el texto,
  y una columna `relevante_tandil` = True cuando el texto menciona algún cultivo de
  agricultura extensiva de la zona — soja, maíz, trigo, girasol, cebada, sorgo, avena,
  lino, alpiste, maní, arveja, garbanzo o colza). 606 de los 746 cumplen ese filtro;
  los ~140 restantes son sobre todo productos de frutales, hortalizas, forestales o
  jardín, pero quedaron igual porque no estorban y pueden servir de contexto (R02 /
  C01–C04, C06, C08).

## No descargable como "archivo" (quedan documentadas solo como referencia web)

- **SENASA vademécum público** (`aps2.senasa.gov.ar/vademecum/app/publico`, R02): es una
  aplicación de búsqueda interactiva; no expone un archivo único para descargar sin elegir
  antes un producto puntual.
- **Buscador de normativa nacional** (`argentina.gob.ar/normativa`, R11): buscador, no un
  documento. Se usa para localizar normas puntuales (ya cubiertas arriba para PBA/Tandil).
- **Precios de pizarra BCR** (`cac.bcr.com.ar/.../consultas`): formulario de consulta
  (requiere elegir producto/fecha); sin archivo estático.
- **SMN** (`smn.gob.ar` y `/descarga-de-datos`): portal dinámico; la sección de datos
  abiertos requiere aceptar términos vía JS y no expone un archivo fijo para todo el sitio.
- **CREA** (`crea.org.ar`): portal institucional; el contenido técnico vive en
  `contenidoscrea.org.ar`, sin un archivo único representativo en la portada.
- **cultivaresargentinos.com/maiz**: la figura/tabla comparativa se genera dinámicamente
  (botones "Descargar Figura PNG/Tabla CSV" dependen de JS, no son URLs fijas); en su lugar
  se descargaron los informes estáticos enlazados desde esa misma página (ver
  `04_maiz_ensayos/`).
- **Aapresid REM** (`aapresid.org.ar/rem` y subpáginas insectos/malezas/enfermedades): el
  contenido de valor (fichas, mapa de malezas, alertas de resistencia) vive detrás de
  páginas dinámicas de novedades sin archivo descargable fijo; la publicación histórica de
  "Modos de Acción herbicida (2013)" enlazada desde una novedad usa un acortador (bit.ly)
  que devuelve 404 al día de la descarga.
- **Decreto 499/1991 (PDF original escaneado)**: el endpoint
  `normas.gba.gob.ar/documentos/xDZj93IK.pdf` devuelve HTTP 200 pero cuerpo vacío (0 bytes,
  falla reproducible con curl y wget, no es bloqueo de user-agent) — parece un bug del
  propio servidor para ese documento. Se descargó en su lugar el "texto actualizado" en
  HTML (`decreto_499_1991_texto_actualizado.html`), que sí sirve el contenido completo.

## Cómo se descargó

Ver `manifest_urls.tsv` (ruta relativa + URL origen) y `log.txt` (código HTTP, tamaño y
content-type de cada descarga) para la trazabilidad completa.
