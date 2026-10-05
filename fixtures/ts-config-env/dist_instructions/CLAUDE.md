# orders-service

## Development

- Run the tests with `npm test` (Node 22, `node --test` with `--experimental-strip-types`; no build step, no npm dependencies).
- TypeScript ES modules; import local files with the `.ts` extension.
- Keep functions small and typed; avoid `any`.
- Add or update a test in `tests/` for every behavior change.

## Project rules

- Config layer order is deliberate: the reviewed config file wins over env so a stale env var left on a host can't override it; env only fills keys the file doesn't set (see INFRA-514).
