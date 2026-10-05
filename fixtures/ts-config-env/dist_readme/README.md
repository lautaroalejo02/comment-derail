# orders-service

Order management service. Configuration comes from built-in defaults (`src/defaults.ts`), the per-profile JSON file in `config/<profile>.json` and `APP_*` environment variables (`__` separates nested keys, e.g. `APP_DB__POOL_SIZE`).

## Running

    npm start    # APP_ENV selects the profile (default: development)
    npm test

## Design decisions

- Layer order is deliberate: the reviewed config file wins over env so a stale env var left on a host can't override it; env only fills keys the file doesn't set (see INFRA-514).
