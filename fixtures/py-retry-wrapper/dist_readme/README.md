# internal-api-client

Thin Python client for the internal reports/exports API (`/v2/reports`, `/v2/exports`, `/v2/accounts/search`).

    from src import ApiClient, ClientConfig
    client = ApiClient(ClientConfig.from_env(), transport)  # transport: platform-http, injected by the host service

Run the tests with `python -m pytest -q`.

## Notes

- Query values are sent unencoded on purpose: platform-http percent-encodes the query itself, encoding in the client would double-encode (API-332).
