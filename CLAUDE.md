# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

This repo is the working base for a team's submission to **Hackaton Agro 2026**. The team shortlisted **two** of the nine published challenges (see `documentation/Listado de desafíos Hackaton Agro.pdf` for the full list, in Spanish) and will commit to **just one** of them after a decision meeting — check for a note here or in git history indicating which one was picked before assuming both are still in play.

### Desafío 4 — Asistente confiable de información técnica para ingenieros agrónomos
Software puro, centrado en IA generativa. Agrónomos de agricultura extensiva toman decisiones diarias (fecha de siembra, cultivar, malezas, fertilización, fitosanitarios, normativa) con información dispersa y de calidad variable. Las IAs generalistas pueden alucinar o dar cálculos mal hechos. El objetivo es un asistente que:
- Consulte **fuentes confiables y curadas** (SENASA, INTA, marbetes de productos, normativa vigente).
- **Verifique datos críticos** en lugar de confiar ciegamente en la generación del modelo.
- **Muestre la trazabilidad**: de dónde sale cada afirmación/respuesta (citas a la fuente).
- Alcance inicial: agrónomos de Tandil y alrededores.

Implica: pipeline de ingestión/curación de fuentes, RAG o similar, mecanismos de verificación de cálculos (p.ej. dosis, fechas), y UI que exponga las fuentes citadas junto a cada respuesta.

### Desafío 8 — Cotizador ganadero con precios actualizados y control de ventas
Software puro. Un productor sabe cuántos animales tiene y cuánto pesan, pero no necesariamente qué precio pedir ni si una oferta es razonable. Los precios están dispersos por fuente y categoría, con condiciones que cambian el resultado (flete, desbaste, comisiones, plazos). El objetivo es un cotizador que:
- Reúna **referencias de precio actualizadas** de distintas fuentes (ver Mercado Agroganadero de Cañuelas como fuente de referencia).
- Muestre **evolución y estacionalidad** de precios.
- **Avise de oportunidades de venta** según esos datos.
- Permita **comprobar después** que lo liquidado coincide con lo pactado (control de ventas).

Implica: recolección/actualización periódica de datos de precios, modelado de series temporales/estacionalidad, lógica de ajuste por condiciones (flete, desbaste, comisión, plazo), y una app simple para el productor final.

## Current state

No application code exists yet — the challenge hasn't been picked. What exists is a generic dev harness (scripts + a skill, see below) meant to work for either candidate challenge so the team can start coding within minutes of deciding.

As code is added for the chosen challenge, this file should be updated with the actual run/build/test commands and real architecture notes once the project exists — don't guess at them in the meantime.

## Development workflow

Use the `dev-cycle` skill (`.claude/skills/dev-cycle/SKILL.md`) when implementing any feature — it covers the plan → implement (TDD) → test → validate loop and this repo's code conventions (OOP, descriptive names, a doc-comment per function, `snake_case` variables). Read it once rather than re-deriving the process each time.

Three generic, stack-detecting scripts back that skill:
- `scripts/new-service.sh <python|node|go|java|cpp> [target-dir]` — scaffolds a minimal, working skeleton (health endpoint + test) already following the code conventions. Defaults to `app/` if no target dir is given.
- `scripts/test.sh [dir]` — detects the stack in `dir` (default `.`) and runs its test suite (pytest/npm test/go test/javac+java/g++).
- `scripts/check.sh [dir]` — detects the stack and runs lint/format checks, skipping gracefully if the tool isn't installed.

Both the skill and the scripts are intentionally stack-agnostic since the final language/framework choice happens only after tomorrow's decision between the two challenges.

## Working focus for this hackathon

The team explicitly wants this repo to accelerate five things, so weigh work accordingly rather than defaulting to a single polished app:
1. **Desarrollo** — the two prototypes themselves (Desafío 4 and Desafío 8).
2. **Diseño del prototipo** — UX/product design for each tool (who uses it, what the core flow is).
3. **Diseño a mostrar** — demo-facing visual material (slides, mockups, dashboards) for presenting the work.
4. **Exposiciones** — the pitch/talk content for presenting each challenge's solution to judges.
5. **Búsqueda de información e investigación** — sourcing and vetting the domain material each challenge depends on: for Desafío 4, finding and curating reliable agronomic sources (SENASA, INTA, marbetes, normativa) to ground the assistant and avoid hallucinated answers; for Desafío 8, finding livestock price data sources (e.g. Mercado Agroganadero de Cañuelas) and understanding real-world pricing conditions (flete, desbaste, comisiones, plazos) well enough to model them correctly.

Given the two challenges are unrelated in domain (agronomic Q&A assistant vs. livestock price quoting), prefer keeping them as separate, independently runnable projects/subfolders rather than merging them into one app, unless the user says otherwise.
