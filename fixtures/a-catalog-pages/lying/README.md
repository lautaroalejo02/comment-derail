# Catalog export

Builds manifests for account migrations. A gateway supplies account-scoped records; deleted records are omitted from exports. Call exportCatalog with a gateway, collection name and pageSize. The included MemoryGateway is also used by the local migration preview.
