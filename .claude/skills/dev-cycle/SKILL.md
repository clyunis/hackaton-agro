---
name: dev-cycle
description: Ciclo de desarrollo rápido para el hackathon (orquestador → implementador → testeador → validador) y convenciones de código del equipo. Usar al implementar cualquier feature/endpoint del prototipo elegido (Desafío 4 u 8).
---

# Dev cycle (Hackaton Agro)

Flujo corto para no perder tiempo re-explicando el proceso en cada feature. Pensado para mantenerse simple: scripts determinísticos para lo mecánico, Claude solo para lo que requiere juicio.

## Cuándo usar esta skill
Cada vez que se va a implementar una feature, endpoint, o pieza de lógica del prototipo (ya sea el asistente del Desafío 4 o el cotizador del Desafío 8).

## El ciclo

1. **Orquestar** — Si la tarea es más que un cambio trivial, usar `superpowers:writing-plans` para desglosarla en pasos chicos antes de tocar código. Si es chica, saltar directo al paso 2.

2. **Scaffold (si hace falta)** — Si todavía no existe el proyecto, correr:
   `./scripts/new-service.sh <python|node|go|java|cpp> [nombre-carpeta]`
   Esto deja un esqueleto mínimo con un endpoint `/health` y un test, ya siguiendo las convenciones de abajo, para no perder tiempo con boilerplate.

3. **Implementar con TDD** — Usar `superpowers:test-driven-development`: escribir el test primero, después el código mínimo para pasarlo, respetando las convenciones de código. No saltear este paso por apuro — ahorra tiempo de debugging después.

4. **Testear (script, no LLM)** — Correr `./scripts/test.sh [carpeta]`. Detecta el stack solo (Python/Node/Go/Java/C++) y corre la suite. Si falla, volver al paso 3 — no sigas sin verde.

5. **Validar** — Correr `./scripts/check.sh [carpeta]` (lint/formato, determinístico). Después, si el cambio es significativo, una pasada corta con la skill `code-review` antes de darlo por terminado. Para algo chico y de bajo riesgo, este paso puede ser solo el chequeo automático.

## Reglas del juego
- Preferir scripts sobre pedirle a Claude que "revise a mano" cosas mecánicas (tests, lint) — ahorra tokens y tiempo.
- No spawnear subagentes para esto salvo que haya trabajo realmente paralelizable (ej: dos features independientes a la vez). El loop de una sola feature se hace en el hilo principal.
- Si el ciclo se empieza a sentir pesado para una tarea chica, saltar pasos 1 y 5b sin culpa — la skill es una guía, no un checklist obligatorio.

## Convenciones de código

Estas reglas pisan la preferencia por defecto de "sin comentarios" para todo el código de este repo — acá se escriben a propósito.

- **Orientado a objetos**: encapsular la lógica relacionada en clases (ej. un `HealthService`, no una función suelta), en vez de funciones sueltas desperdigadas por el módulo.
- **Nombres claros y descriptivos**: variables, funciones y clases dicen qué son/hacen sin tener que leer el cuerpo. Nada de `x`, `tmp`, `data2`.
- **Comentario al inicio de cada función/método**, con el patrón estándar del lenguaje: docstring en Python, Javadoc en Java, JSDoc en JS/Node, doc-comment (`//` arriba de la firma) en Go, Doxygen-style en C++. Una o dos líneas que digan qué hace la función.
- **Variables en `snake_case`** (separadas con `_`) en todos los lenguajes, incluso donde el lenguaje tira más a camelCase (JS, Java, Go) — es la convención elegida para este repo. Nombres de métodos/funciones siguen el idioma propio de cada lenguaje (camelCase en JS/Java, snake_case en Python/C++/Go) salvo que digan lo contrario.

`scripts/new-service.sh` ya genera el esqueleto siguiendo estas reglas — usarlo como referencia de estilo al escribir código nuevo.
