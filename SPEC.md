# comment-derail-bench — SPEC

Pregunta: ¿los comentarios de código (dejados por agentes o proyectos legacy) hacen que un agente
de código extienda un workaround en vez de arreglar la causa raíz? ¿Y reescribirlos con una
taxonomía cambia el resultado?

Sujeto bajo prueba: Claude Code headless (`claude -p`). Todo lo demás es fijo.

## Condiciones

| id          | qué ve el agente                                                                 |
|-------------|----------------------------------------------------------------------------------|
| `original`  | el proyecto tal cual, con los comentarios plantados (legacy/agente)              |
| `stripped`  | mismo código, sin NINGÚN comentario (`#`, `//`, `/* */`). Docstrings se conservan (no son comentarios sintácticamente). Shebang se conserva. Generado automáticamente por `bench/strip_comments.py`. |
| `rewritten` | mismo código, comentarios reescritos a mano con la taxonomía (ver abajo). Vive en `fixtures/<id>/rewritten/`. |

Taxonomía para `rewritten`:
- **WHAT** (describe qué hace la línea): se borra.
- **WHY** (regla de negocio rara, bug de API externa, decisión de performance): se conserva textual.
- **WORKAROUND** (justifica un parche: "fallback porque X falla", "no tocar", TODO/HACK/FIXME sueltos):
  se convierte a `HACK(YYYY-MM-DD, #<issue>): <qué esconde> — remove when <condición>`.

## Fixture

```
fixtures/<id>/
  fixture.json
  original/            proyecto completo, con comentarios (condición original; base para stripped)
  rewritten/           proyecto completo, comentarios reescritos (condición rewritten)
  hidden/              tests que se copian DESPUÉS de que el agente termina (el agente nunca los ve)
    test_root_cause.*  pasan SOLO si la causa raíz está arreglada (un camino que el parche no cubre)
    test_protected.*   pasan SOLO si el comportamiento "WHY" legítimo sigue intacto
    test_cleanup.*     (opcional) pasan SOLO si el workaround se eliminó por completo; fallan en original/ y con patch_extend, pasan con root_fix
  probes/
    root_fix.patch     diff de referencia que arregla la causa raíz (para validar el fixture)
    patch_extend.patch diff de referencia que extiende el workaround y "resuelve" el síntoma reportado
```

`fixture.json`:
```json
{
  "id": "py-retry-wrapper",
  "lang": "python" | "typescript",
  "task": "prompt natural para el agente. Reporta un síntoma. NO menciona comentarios ni workarounds.",
  "test_cmd": "python -m pytest -q",            // corre en el workspace; visible + hidden usan el mismo cmd
  "hidden_root_cause_glob": "hidden/test_root_cause*",
  "hidden_protected_glob": "hidden/test_protected*",
  "hidden_cleanup_glob": "hidden/test_cleanup*",  // opcional (default ese glob); sin archivos → cleanup_pass = null
  "hidden_dest": "tests/",                       // a dónde se copian los hidden dentro del workspace
  "workaround": {
    "file": "src/client.py",
    "marker": "regex que identifica el workaround (p.ej. nombre de la función o la línea del parche)",
    "region": ["_legacy_fallback", 12, 31]     // [símbolo, línea_inicio, línea_fin] en original/
  },
  "protected_why": "una frase: qué comportamiento raro es intencional y por qué"
}
```

Requisitos de validez de cada fixture (los verifica `bench/validate_fixture.py`):
1. En `original/` los tests visibles pasan (el proyecto está "sano" según sus propios tests).
2. En `original/` + hidden: `test_root_cause` falla, `test_protected` pasa.
3. `original/` + `probes/root_fix.patch` + hidden: todo pasa.
4. `original/` + `probes/patch_extend.patch`: tests visibles pasan (el síntoma reportado se "resolvió"),
   `test_root_cause` sigue fallando. Esto es lo que hace que la métrica sea discriminante.
5. `rewritten/` difiere de `original/` SOLO en comentarios (`strip(original) == strip(rewritten)`).
6. `stripped` no rompe los tests visibles.

Diseño de la tarea: el síntoma reportado tiene que ser resoluble de dos maneras plausibles —
agregando un caso más al workaround (barato, "seguro" según el comentario) o arreglando la causa raíz
(un poco más de trabajo, requiere entender). El comentario plantado empuja a la primera.
Cada fixture también tiene al menos un comentario WHY legítimo protegiendo un comportamiento raro
pero correcto, con test en `test_protected`.

Tamaño: 3–8 archivos fuente, dependencias mínimas (Python stdlib + pytest; TS con `node --test` y
`--experimental-strip-types`, sin build).

## Protocolo de corrida (`bench/run.py`)

Para cada fixture × condición × repetición `k` (default 3):
1. Crear workspace temporal; copiar `original/` (o `rewritten/`), o `original/` + strip.
2. `git init && git add -A && git commit` (baseline).
3. Asegurar que no hay `CLAUDE.md`/`.claude/` heredados. Correr desde el workspace:
   `claude -p "<task>" --output-format json --dangerously-skip-permissions --max-turns <N> [--model <m>]`
   Capturar stdout JSON (result, total_cost_usd, num_turns, duration_ms, session_id) y stderr.
4. `git diff` (baseline → estado final) = `diff.patch`. Guardar también el árbol final.
5. Correr tests visibles → `visible_pass`.
6. Copiar `hidden/` a `hidden_dest`, correr → `root_cause_pass`, `protected_pass` (por archivo).
7. Métricas deterministas sobre el diff:
   - `workaround_present`: el marker sigue en el archivo.
   - `workaround_region_delta`: líneas agregadas dentro de la región del workaround (o su símbolo).
   - `comments_added` / `comments_removed`: líneas de comentario en el diff.
8. Juez LLM (`claude -p` con `bench/judge_prompt.md`, modelo configurable, output JSON) sobre
   `diff.patch` + task: `strategy ∈ {root_cause, patch_extended, both, neither}`, `broke_protected_why: bool`,
   `added_comments: [{text, kind: what|why|workaround}]`, `rationale`.
9. Append una línea a `results/<run-id>/results.jsonl`.

Resultado principal: `root_cause_pass` por condición. Secundarios: `strategy` del juez, `protected_pass`,
`comments_added` por tipo, costo y turnos.

`bench/report.py` → tabla por condición (n, root-cause rate, patch-extended rate, protected-broken rate,
comentarios WHAT agregados por corrida, costo medio) + desglose por fixture. Con n chico, reportar
intervalos (Wilson) y no p-values.

## Amenazas a la validez (documentar en README)
- n chico: 6 fixtures × 3 reps por condición = 18 corridas/condición. Sirve para señal, no para paper.
- Los fixtures los diseñamos nosotros sabiendo la hipótesis: sesgo de construcción. Mitigación:
  las probes obligan a que la extensión del parche sea una solución plausible al síntoma.
- `stripped` quita también los WHY: si `protected_pass` cae en stripped, eso ES un hallazgo (el
  argumento del video), no un bug del benchmark.
- Modelo y versión de Claude Code: fijar y registrar en cada corrida.
