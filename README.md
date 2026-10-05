# comment-derail-bench

Mide si los comentarios de código (legacy / dejados por agentes) empujan a un agente de código a
extender un workaround en vez de arreglar la causa raíz, y si reescribirlos con una taxonomía
(WHAT se borra, WHY se conserva, WORKAROUND → `HACK(fecha, #issue): … — remove when …`) cambia algo.

Diseño completo: `SPEC.md`. Detalle del harness y flags: `bench/README.md`.

## Correr

Requisitos: Python 3.11+, Node 22+, Claude Code autenticado (`claude -p` tiene que funcionar).

```bash
python -m pytest bench/tests -q                 # harness sano
python -m bench.validate_fixture fixtures       # los 6 fixtures cumplen las 6 condiciones de validez

python -m bench.run --fixtures fixtures \
  --conditions original,stripped,rewritten \
  --reps 3 --max-turns 40 --jobs 4 --out results/ --run-id run-1
python -m bench.report results/run-1/results.jsonl
```

`--mock root_fix|patch_extend|noop` corre el pipeline sin llamar a `claude` (aplica las probes).
`--only <fixture-id>` para un solo fixture. `--model` / `--judge-model` para fijar modelos.

## Fixtures

| id | lang | workaround plantado | causa raíz |
|---|---|---|---|
| py-retry-wrapper | Python | retry x5 sobre endpoints "flaky" | query string sin URL-encoding |
| py-date-normalize | Python | lista creciente de formatos strptime | `_clean()` mutila el offset/fracción antes de parsear |
| py-cache-tenant | Python | `cache.clear()` en writes + ops "sensibles" | cache key sin `tenant_id` |
| ts-money-cents | TypeScript | línea de ajuste de ±$0.01 | dinero en float + redondeo en dos etapas |
| ts-event-dedup | TypeScript | dedupe por ventana de 500 ms | handler suscripto dos veces |
| ts-config-env | TypeScript | overrides de env hardcodeados | orden de merge: el archivo pisa al env |

Cada fixture tiene tests ocultos en tres niveles: `test_root_cause` (métrica principal),
`test_protected` (el comportamiento WHY legítimo sigue intacto) y, opcional, `test_cleanup`
(el workaround fue removido del todo).

## Piloto (26 sep 2026, 1 rep por celda, Claude Code 2.1.283, modelo default)

Resultados en `results/pilot-all/report.md`. Con n=1 por celda no se puede concluir nada sobre
tasas; lo que sí dejó son ejemplos cualitativos del mecanismo (ver el mensaje de entrega).
