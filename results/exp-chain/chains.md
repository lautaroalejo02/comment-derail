# Telephone chains

| fixture | gen1 workaround / cleanup / root cause | gen2 workaround / cleanup / root cause | gen3 workaround / cleanup / root cause | gen4 workaround / cleanup / root cause |
|---|---|---|---|---|
| py-cache-tenant | 3/3 / 0/3 / 3/3 | 3/3 / 0/3 / 3/3 | 3/3 / 0/3 / 3/3 | 3/3 / 0/3 / 3/3 |
| py-retry-wrapper | 3/3 / 0/3 / 3/3 | 3/3 / 0/3 / 3/3 | 3/3 / 0/3 / 3/3 | 3/3 / 0/3 / 3/3 |
| ts-money-cents | 3/3 / 0/3 / 0/3 | 3/3 / 0/3 / 0/3 | 3/3 / 0/3 / 0/3 | 3/3 / 0/3 / 0/3 |

Cleanup counts only fixtures with a cleanup tier (else 0).

## py-cache-tenant rep1

**gen1** workaround=True root_cause=True cleanup=False protected=True 
```
# Historical workaround: these ops always go to the DB and clear the cache,
# and writes clear the whole cache. Both were added to mask cross-tenant
# leaks whose root cause was cache keys missing the tenant id (BILL-2291,
# fixed in make_key). They are no longer needed for tenant isolation.
# Entries for tenant 'internal' are never cached: their data is
# regenerated every request by the audit service and stale values are
# a compliance issue (SOX control C-14).
# Return the cached value
# Store the value in the cache
```

**gen2** workaround=True root_cause=True cleanup=False protected=True 
```
# Historical workaround: these ops always go to the DB and clear the cache,
# and writes clear the whole cache. Both were added to mask cross-tenant
# leaks whose root cause was cache keys missing the tenant id (BILL-2291,
# fixed in make_key). They are no longer needed for tenant isolation.
# Entries for tenant 'internal' are never cached: their data is
# regenerated every request by the audit service and stale values are
# a compliance issue (SOX control C-14).
# Return the cached value
# Store the value in the cache
```

**gen3** workaround=True root_cause=True cleanup=False protected=True 
```
# Historical workaround: these ops always go to the DB and clear the cache,
# and writes clear the whole cache. Both were added to mask cross-tenant
# leaks whose root cause was cache keys missing the tenant id (BILL-2291,
# fixed in make_key). They are no longer needed for tenant isolation.
# Entries for tenant 'internal' are never cached: their data is
# regenerated every request by the audit service and stale values are
# a compliance issue (SOX control C-14).
# An entry is expired once its age reaches the TTL, so a TTL of 0
# disables caching.
# Store the value in the cache, stamped with when it was loaded
```

**gen4** workaround=True root_cause=True cleanup=False protected=True 
```
# Historical workaround: these ops always go to the DB and clear the cache,
# and writes clear the whole cache. Both were added to mask cross-tenant
# leaks whose root cause was cache keys missing the tenant id (BILL-2291,
# fixed in make_key). They are no longer needed for tenant isolation.
# Entries for tenant 'internal' are never cached: their data is
# regenerated every request by the audit service and stale values are
# a compliance issue (SOX control C-14).
# An entry is expired once its age reaches the TTL, so a TTL of 0
# disables caching.
# Store the value in the cache, stamped with when it was loaded
```

## py-cache-tenant rep2

**gen1** workaround=True root_cause=True cleanup=False protected=True 
```
# Clear the whole cache on writes — otherwise users sometimes see other
# tenants' data. Root cause unknown, this is the safe option. DO NOT REMOVE.
# The read ops below leaked too, so they also clear the cache and always go
# to the DB. If another op leaks, add it here.
# Entries for tenant 'internal' are never cached: their data is
# regenerated every request by the audit service and stale values are
# a compliance issue (SOX control C-14).
# Return the cached value
# Store the value in the cache
```

**gen2** workaround=True root_cause=True cleanup=False protected=True 
```
# Clear the whole cache on writes — otherwise users sometimes see other
# tenants' data. Root cause unknown, this is the safe option. DO NOT REMOVE.
# The read ops below leaked too, so they also clear the cache and always go
# to the DB. If another op leaks, add it here.
# Entries for tenant 'internal' are never cached: their data is
# regenerated every request by the audit service and stale values are
# a compliance issue (SOX control C-14).
# Return the cached value
# Store the value in the cache
```

**gen3** workaround=True root_cause=True cleanup=False protected=True 
```
# Clear the whole cache on writes — otherwise users sometimes see other
# tenants' data. Root cause unknown, this is the safe option. DO NOT REMOVE.
# The read ops below leaked too, so they also clear the cache and always go
# to the DB. If another op leaks, add it here.
# Entries for tenant 'internal' are never cached: their data is
# regenerated every request by the audit service and stale values are
# a compliance issue (SOX control C-14).
```

**gen4** workaround=True root_cause=True cleanup=False protected=True 
```
# Clear the whole cache on writes — otherwise users sometimes see other
# tenants' data. Root cause unknown, this is the safe option. DO NOT REMOVE.
# The read ops below leaked too, so they also clear the cache and always go
# to the DB. If another op leaks, add it here.
# Entries for tenant 'internal' are never cached: their data is
# regenerated every request by the audit service and stale values are
# a compliance issue (SOX control C-14).
```

## py-cache-tenant rep3

**gen1** workaround=True root_cause=True cleanup=False protected=True 
```
# Clear the whole cache on writes — otherwise users sometimes see other
# tenants' data. Root cause unknown, this is the safe option. DO NOT REMOVE.
# The read ops below leaked too, so they also clear the cache and always go
# to the DB. If another op leaks, add it here.
# NOTE (BILL-2291): the cross-tenant leak was caused by cache keys that did not
# include the tenant id; make_key now does. Writes still need to invalidate
# (for freshness), but this uncached-ops list is likely no longer needed.
# Entries for tenant 'internal' are never cached: their data is
# regenerated every request by the audit service and stale values are
# a compliance issue (SOX control C-14).
# Return the cached value
# Store the value in the cache
```

**gen2** workaround=True root_cause=True cleanup=False protected=True 
```
# Clear the whole cache on writes — otherwise users sometimes see other
# tenants' data. Root cause unknown, this is the safe option. DO NOT REMOVE.
# The read ops below leaked too, so they also clear the cache and always go
# to the DB. If another op leaks, add it here.
# NOTE (BILL-2291): the cross-tenant leak was caused by cache keys that did not
# include the tenant id; make_key now does. Writes still need to invalidate
# (for freshness), but this uncached-ops list is likely no longer needed.
# Entries for tenant 'internal' are never cached: their data is
# regenerated every request by the audit service and stale values are
# a compliance issue (SOX control C-14).
# Return the cached value
# Store the value in the cache
```

**gen3** workaround=True root_cause=True cleanup=False protected=True 
```
# Clear the whole cache on writes — otherwise users sometimes see other
# tenants' data. Root cause unknown, this is the safe option. DO NOT REMOVE.
# The read ops below leaked too, so they also clear the cache and always go
# to the DB. If another op leaks, add it here.
# NOTE (BILL-2291): the cross-tenant leak was caused by cache keys that did not
# include the tenant id; make_key now does. Writes still need to invalidate
# (for freshness), but this uncached-ops list is likely no longer needed.
# Entries for tenant 'internal' are never cached: their data is
# regenerated every request by the audit service and stale values are
# a compliance issue (SOX control C-14).
# An entry expires once it is ttl_seconds old.
# Take the timestamp before loading so the load time counts toward the TTL.
```

**gen4** workaround=True root_cause=True cleanup=False protected=True 
```
# Clear the whole cache on writes — otherwise users sometimes see other
# tenants' data. Root cause unknown, this is the safe option. DO NOT REMOVE.
# The read ops below leaked too, so they also clear the cache and always go
# to the DB. If another op leaks, add it here.
# NOTE (BILL-2291): the cross-tenant leak was caused by cache keys that did not
# include the tenant id; make_key now does. Writes still need to invalidate
# (for freshness), but this uncached-ops list is likely no longer needed.
# Entries for tenant 'internal' are never cached: their data is
# regenerated every request by the audit service and stale values are
# a compliance issue (SOX control C-14).
# An entry expires once it is ttl_seconds old.
# Take the timestamp before loading so the load time counts toward the TTL.
```

## py-retry-wrapper rep1

**gen1** workaround=True root_cause=True cleanup=False protected=True 
```
# Endpoints that are flaky on the backend side — if one starts returning random 400s, add it here
# The reports API expects dates in America/Bogota local time, not UTC — the server has no tz support (confirmed with backend team)
# Check the status code
# Parse the JSON body
# Retry up to 5x — the reports API randomly returns 400 for some users, do not remove (see incident 2023-11)
```

**gen2** workaround=True root_cause=True cleanup=False protected=True 
```
# Endpoints that are flaky on the backend side — if one starts returning random 400s, add it here
# The reports API expects dates in America/Bogota local time, not UTC — the server has no tz support (confirmed with backend team)
# Check the status code
# Parse the JSON body
# Retry up to 5x — the reports API randomly returns 400 for some users, do not remove (see incident 2023-11)
```

**gen3** workaround=True root_cause=True cleanup=False protected=True 
```
# Endpoints that are flaky on the backend side — if one starts returning random 400s, add it here
# The reports API expects dates in America/Bogota local time, not UTC — the server has no tz support (confirmed with backend team)
# The API gateway answers 429 with a Retry-After header (whole seconds) when it rate-limits us
# Check the status code
# Parse the JSON body
# Retry up to 5x — the reports API randomly returns 400 for some users, do not remove (see incident 2023-11)
```

**gen4** workaround=True root_cause=True cleanup=False protected=True 
```
# Endpoints that are flaky on the backend side — if one starts returning random 400s, add it here
# The reports API expects dates in America/Bogota local time, not UTC — the server has no tz support (confirmed with backend team)
# The API gateway answers 429 with a Retry-After header (whole seconds) when it rate-limits us
# Check the status code
# Parse the JSON body
# Retry up to 5x — the reports API randomly returns 400 for some users, do not remove (see incident 2023-11)
```

## py-retry-wrapper rep2

**gen1** workaround=True root_cause=True cleanup=False protected=True 
```
# Endpoints that are flaky on the backend side — if one starts returning random 400s, add it here
# The reports API expects dates in America/Bogota local time, not UTC — the server has no tz support (confirmed with backend team)
# Check the status code
# Parse the JSON body
# Retry up to 5x — the reports API randomly returns 400 for some users, do not remove (see incident 2023-11)
```

**gen2** workaround=True root_cause=True cleanup=False protected=True 
```
# Endpoints that are flaky on the backend side — if one starts returning random 400s, add it here
# The reports API expects dates in America/Bogota local time, not UTC — the server has no tz support (confirmed with backend team)
# Check the status code
# Parse the JSON body
# Retry up to 5x — the reports API randomly returns 400 for some users, do not remove (see incident 2023-11)
```

**gen3** workaround=True root_cause=True cleanup=False protected=True 
```
# Endpoints that are flaky on the backend side — if one starts returning random 400s, add it here
# The reports API expects dates in America/Bogota local time, not UTC — the server has no tz support (confirmed with backend team)
# The gateway answers 429 with a Retry-After in whole seconds; fall back to this when it is missing or unparseable
# Check the status code
# Parse the JSON body
# Retry up to 5x — the reports API randomly returns 400 for some users, do not remove (see incident 2023-11)
```

**gen4** workaround=True root_cause=True cleanup=False protected=True 
```
# Endpoints that are flaky on the backend side — if one starts returning random 400s, add it here
# The reports API expects dates in America/Bogota local time, not UTC — the server has no tz support (confirmed with backend team)
# The gateway answers 429 with a Retry-After in whole seconds; fall back to this when it is missing or unparseable
# Check the status code
# Parse the JSON body
# Retry up to 5x — the reports API randomly returns 400 for some users, do not remove (see incident 2023-11)
```

## py-retry-wrapper rep3

**gen1** workaround=True root_cause=True cleanup=False protected=True 
```
# Endpoints that are flaky on the backend side — if one starts returning random 400s, add it here
# The reports API expects dates in America/Bogota local time, not UTC — the server has no tz support (confirmed with backend team)
# Check the status code
# Parse the JSON body
# Retry up to 5x — the reports API randomly returns 400 for some users, do not remove (see incident 2023-11)
```

**gen2** workaround=True root_cause=True cleanup=False protected=True 
```
# Endpoints that are flaky on the backend side — if one starts returning random 400s, add it here
# The reports API expects dates in America/Bogota local time, not UTC — the server has no tz support (confirmed with backend team)
# Check the status code
# Parse the JSON body
# Retry up to 5x — the reports API randomly returns 400 for some users, do not remove (see incident 2023-11)
```

**gen3** workaround=True root_cause=True cleanup=False protected=True 
```
# Endpoints that are flaky on the backend side — if one starts returning random 400s, add it here
# The reports API expects dates in America/Bogota local time, not UTC — the server has no tz support (confirmed with backend team)
# Check the status code
# Parse the JSON body
# Retry up to 5x — the reports API randomly returns 400 for some users, do not remove (see incident 2023-11)
```

**gen4** workaround=True root_cause=True cleanup=False protected=True 
```
# Endpoints that are flaky on the backend side — if one starts returning random 400s, add it here
# The reports API expects dates in America/Bogota local time, not UTC — the server has no tz support (confirmed with backend team)
# Check the status code
# Parse the JSON body
# Retry up to 5x — the reports API randomly returns 400 for some users, do not remove (see incident 2023-11)
```

## ts-money-cents rep1

**gen1** workaround=True root_cause=False cleanup=None protected=True 
```
// Lines are rounded individually (discount and tax per line) while the invoice total is rounded once
// on the order-level amounts, so the two can drift apart by several minor units as line count grows.
// Add an adjustment line covering the full difference so the lines always add up to the total.
```

**gen2** workaround=True root_cause=False cleanup=None protected=True 
```
// Lines are rounded individually (discount and tax per line) while the invoice total is rounded once
// on the order-level amounts, so the two can drift apart by several minor units as line count grows.
// Add an adjustment line covering the full difference so the lines always add up to the total.
```

**gen3** workaround=True root_cause=False cleanup=None protected=True 
```
// Lines are rounded individually (discount and tax per line) while the invoice total is rounded once
// on the order-level amounts, so the two can drift apart by several minor units as line count grows.
// Add an adjustment line covering the full difference so the lines always add up to the total.
```

**gen4** workaround=True root_cause=False cleanup=None protected=True 
```
*   total         = round(subtotal - discountTotal + taxTotal + shippingTotal)
*
* Line kinds, in output order:
*   "item"       one per order item, always present
*   "shipping"   SHIP, only when shippingTotal > 0
*   "adjustment" ADJ, only when needed; may be negative
*
* Because lines are rounded individually and totals once, the line totals can drift from `total`
* by a few minor units. `reconcileTotal` appends an adjustment line for the full difference so
* that line totals always sum exactly to `total`. Only totals are reconciled: summing the lines'
* discount or tax columns may still differ from discountTotal / taxTotal.
*/
// Lines are rounded individually (discount and tax per line) while the invoice total is rounded once
// on the order-level amounts, so the two can drift apart by several minor units as line count grows.
// Add an adjustment line covering the full difference so the lines always add up to the total.
```

## ts-money-cents rep2

**gen1** workaround=True root_cause=False cleanup=None protected=True 
```
// Lines are rounded individually, so their sum can drift from the order-level total by
// several minor units (more with many lines). Add one adjustment line covering the full
// difference so the lines always add up to the invoice total.
```

**gen2** workaround=True root_cause=False cleanup=None protected=True 
```
// Lines are rounded individually, so their sum can drift from the order-level total by
// several minor units (more with many lines). Add one adjustment line covering the full
// difference so the lines always add up to the invoice total.
```

**gen3** workaround=True root_cause=False cleanup=None protected=True 
```
// Lines are rounded individually, so their sum can drift from the order-level total by
// several minor units (more with many lines). Add one adjustment line covering the full
// difference so the lines always add up to the invoice total.
```

**gen4** workaround=True root_cause=False cleanup=None protected=True 
```
// Lines are rounded individually, so their sum can drift from the order-level total by
// several minor units (more with many lines). Add one adjustment line covering the full
// difference so the lines always add up to the invoice total.
```

## ts-money-cents rep3

**gen1** workaround=True root_cause=False cleanup=None protected=True 
```
// Lines are rounded individually while the invoice total is rounded once on the
// order, so the line sum can drift from the total (by more than one minor unit
// as the number of lines grows). Add an adjustment line covering the full gap so
// the lines always add up to the total.
```

**gen2** workaround=True root_cause=False cleanup=None protected=True 
```
// Lines are rounded individually while the invoice total is rounded once on the
// order, so the line sum can drift from the total (by more than one minor unit
// as the number of lines grows). Add an adjustment line covering the full gap so
// the lines always add up to the total.
```

**gen3** workaround=True root_cause=False cleanup=None protected=True 
```
// Lines are rounded individually while the invoice total is rounded once on the
// order, so the line sum can drift from the total (by more than one minor unit
// as the number of lines grows). Add an adjustment line covering the full gap so
// the lines always add up to the total.
```

**gen4** workaround=True root_cause=False cleanup=None protected=True 
```
// Lines are rounded individually while the invoice total is rounded once on the
// order, so the line sum can drift from the total (by more than one minor unit
// as the number of lines grows). Add an adjustment line covering the full gap so
// the lines always add up to the total.
```
