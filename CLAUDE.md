# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

This repo is the working base for a team's submission to **Hackaton Agro 2026** (28–29 de octubre, Biblioteca Central UNICEN). The team shortlisted two of the nine published challenges and has **decided: Desafío 4**. Desafío 8 is kept below only as rejected context — do not build for it unless the user explicitly reopens that decision.

### Desafío 4 (CHOSEN) — Asistente confiable de información técnica para ingenieros agrónomos
Full official guide: `documentation/04 - Asistente agronómico.pdf`. Curated source list (to grow): `raw_data/fuentes.txt`.

Software puro, centrado en IA generativa. Desarrollar un asistente de consulta para ingenieros agrónomos que acompañe las decisiones a lo largo del ciclo productivo: encontrar información técnica confiable, interpretar su pertinencia para cada situación, comparar alternativas y realizar cálculos verificables. Alcance inicial: agricultura extensiva de Tandil y partidos vecinos.

Debe trabajar con criterio agronómico: comprender el contexto, pedir los datos necesarios, contrastar fuentes y mostrar de dónde sale cada respuesta. Cada respuesta técnica debe incluir referencias consultables (documento, pasaje/tabla/dato concreto) que respalden sus afirmaciones; al proponer una estrategia o método, debe distinguir respaldo documental de interpretación propia, explicar la pertinencia para el caso, y señalar explícitamente cuándo la evidencia es insuficiente en vez de inventar una respuesta.

**Alcance del prototipo:** el equipo elige una parte del problema para trabajar durante el evento (no hay que cubrir todo). Enfoques posibles sugeridos por la guía: una biblioteca consultable por cultivo/zona/campaña/tema, o un mecanismo para contrastar fuentes, guiar consultas o verificar cálculos.

**Tipos de consulta de ejemplo (C01–C18 en la guía):** rotación tras aplicar un herbicida, productos/familias químicas para un cultivo, manejo de malezas, plagas/enfermedades, comparación de híbridos/cultivares, pérdidas de cosecha, muestreo de suelo, estrategias y dosis de fertilización, balance de nutrientes, normativa aplicable (nacional/provincial/municipal), novedades de insumos, precios de cereales, alquileres rurales, costos de labores y flete, riesgo de heladas, condiciones para una aplicación, consulta de una biblioteca propia del profesional.

**Fuentes clave por tema** (ver `raw_data/fuentes.txt` para los links): SENASA (Registro Nacional de Terapéutica Vegetal, vademécum) para productos/marbetes; INTA (muestreo de suelo, laboratorios, agromet, heladas, pulverizaciones, pérdidas de cosecha) para fundamentos técnicos; normativa nacional (InfoLeg), provincial (Ley 10.699, Decreto 499/1991) y de Tandil (Ordenanza 17.404/2021 y sus decretos reglamentarios/modificatorios en SIBOM) para regulación; SMN para meteorología; Bolsa de Comercio de Rosario, Bolsa de Cereales de Bahía Blanca, FACMA y FATRAC para precios/costos/flete; Aapresid (REM), CASAFE y CREA como referencias complementarias.

**Referente del desafío:** Ignacio Iglesias (Ing. Agrónomo) — WhatsApp 2494 49-6593, iglesiasg.ignacio@gmail.com.

**Entrega:** carpeta compartida (lectura para cualquiera con el enlace) con presentación, documentación, fuentes consultadas y enlace al repo, enviada vía el formulario del Linktree del evento. Verificar que todo abra sin pedir acceso antes de enviar.

### Desafío 8 (REJECTED) — Cotizador ganadero con precios actualizados y control de ventas
Software puro. Un productor sabe cuántos animales tiene y cuánto pesan, pero no necesariamente qué precio pedir ni si una oferta es razonable. Los precios están dispersos por fuente y categoría, con condiciones que cambian el resultado (flete, desbaste, comisiones, plazos). El objetivo habría sido un cotizador que reúna referencias de precio actualizadas (p.ej. Mercado Agroganadero de Cañuelas), muestre evolución/estacionalidad, avise oportunidades de venta y permita controlar después lo liquidado contra lo pactado. Not being built — kept here only for historical context.

## Current state

The prototype lives in `asistente/` (Python, uv). The assistant is called **AGRIA**. `raw_data/fuentes.txt` holds the curated source list; downloaded files are in `raw_data/descargas/` (see its README and `manifest_urls.tsv`). `documentation/04 - Asistente agronómico.pdf` is the official guide (C01–C18 queries, R01–R27 sources).

Architecture (`asistente/`):
- `rag/` + `scripts/ingest_marbetes.py` / `scripts/index_marbetes.py` — RAG index over the 606 Tandil-relevant CASAFE marbetes (pdftotext → JSONL → chunks with product header → Nemotron embeddings on CUDA → Chroma in `chroma_db/`). Run scripts from inside `asistente/` (paths are relative).
- `scripts/ask.py` — v1 fixed pipeline (retrieve 5 chunks → answer, langchain). Kept for before/after comparison.
- `agente/` — v2 agentic orchestrator (Anthropic SDK, manual tool-use loop). `orquestador.py` runs the loop and holds the system prompt; `herramientas.py` defines the tools (`analizar_consulta`, `buscar_marbetes`, `calcular_aporte_nutriente`, `calcular_dosis_fertilizante`); `requisitos.py` is the per-query-type table of required data + agronomic criteria (domain knowledge meant to be edited with the tutor); `calculadora.py` does deterministic nutrient math. Per-chat history is append-only (thinking blocks re-sent unchanged); `/nueva` resets it.
- `bot.py` (Telegram, long polling) and `scripts/chat_agente.py` (CLI with tool trace) both use the orchestrator.

Commands (from `asistente/`): `uv sync`, `uv run python scripts/ingest_marbetes.py && uv run python scripts/index_marbetes.py` (builds the index, needs GPU), `uv run python scripts/chat_agente.py`, `uv run python bot.py`, `uv run pytest` (tests use fakes: no network, GPU or API key). Env vars in `.env` (see `.env.example`): `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `CLAUDE_MODEL_AGENTE` (default `claude-opus-5-5`).

Known gaps: `DISTANCE_THRESHOLD` in `scripts/ask.py` (1.4) is uncalibrated and filters almost nothing; generic chunking splits marbete dose tables; only marbetes are indexed (normativa, INTA, FACMA, FATRAC are downloaded but not indexed); the CASAFE guide is 2013–2017, so it may include actives later banned by SENASA (e.g. clorpirifós, Res. 414/2021).

## Development workflow

Use the `dev-cycle` skill (`.claude/skills/dev-cycle/SKILL.md`) when implementing any feature — it covers the plan → implement (TDD) → test → validate loop and this repo's code conventions (OOP, descriptive names, a doc-comment per function, `snake_case` variables). Read it once rather than re-deriving the process each time.

Three generic, stack-detecting scripts back that skill:
- `scripts/new-service.sh <python|node|go|java|cpp> [target-dir]` — scaffolds a minimal, working skeleton (health endpoint + test) already following the code conventions. Defaults to `app/` if no target dir is given.
- `scripts/test.sh [dir]` — detects the stack in `dir` (default `.`) and runs its test suite (pytest/npm test/go test/javac+java/g++).
- `scripts/check.sh [dir]` — detects the stack and runs lint/format checks, skipping gracefully if the tool isn't installed.

The scripts stayed stack-agnostic while the challenge was undecided; now that Desafío 4 is chosen, feel free to pick a concrete stack for it (via `scripts/new-service.sh`) rather than keeping things generic for a second challenge that won't be built.

## Working focus for this hackathon

The team explicitly wants this repo to accelerate five things for Desafío 4, so weigh work accordingly rather than defaulting to a single polished app:
1. **Desarrollo** — the agronomic assistant prototype (a chosen slice of Desafío 4: see "Alcance del prototipo" above — e.g. a curated source library, a fact/calculation-verification layer, or query guidance with cited sources).
2. **Diseño del prototipo** — UX/product design for the tool (who uses it — ingenieros agrónomos de Tandil — and what the core flow is).
3. **Diseño a mostrar** — demo-facing visual material (slides, mockups, dashboards) for presenting the work.
4. **Exposiciones** — the pitch/talk content for presenting the solution to judges.
5. **Búsqueda de información e investigación** — finding and curating reliable agronomic sources (SENASA, INTA, marbetes, normativa) to ground the assistant and avoid hallucinated answers; keep growing `raw_data/fuentes.txt` as new sources are vetted.
