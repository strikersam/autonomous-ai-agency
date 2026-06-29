---
title: ADR-007: Storage backend duck-typing over formal ABC
status: accepted
date: 2026-06-28
---

# ADR-007: Storage backend duck-typing over formal ABC

## Context

Phase 5 moved `db/mongo_store.py` → `packages/storage/mongo.py` and
`db/sqlite_store.py` → `packages/storage/sqlite.py`. The original
Phase 5 plan called for a formal `StorageInterface` ABC that both
backends would subclass.

## Decision

**Use duck-typing (Protocol), not a formal ABC.** Both backends expose
collections via attribute access (the Motor `AsyncIOMotorDatabase`
pattern):

```python
store = get_store()  # MongoStore or SQLiteStore
user = await store.users.find_one({"email": "x@y.com"})
await store.tasks.insert_one({...})
```

`StorageInterface` is documented as a `Protocol` (in
`packages/storage/interface.py`) — both backends satisfy it
structurally without inheriting it.

## Rationale

1. **Motor's API is large + dynamically dispatched.** Wrapping every
   method (`find_one`, `find`, `insert_one`, `update_one`, `delete_one`,
   `delete_many`, `count_documents`, `create_index`, `aggregate`,
   `find_one_and_update`, `find_one_and_replace`, `find_one_and_delete`,
   `bulk_write`, `replace_one`, `drop`, `list_indexes`, …) through an
   ABC would add a method-call indirection on every DB operation.

2. **The hot path matters.** The agency loop calls `find_one` /
   `update_one` hundreds of times per minute. A 5µs ABC dispatch
   overhead × 100 calls/min × 1440 min/day = ~720ms/day wasted per
   worker process. Small, but pointless when the ABC adds no safety.

3. **The contract is already enforced by tests.** Every collection
   access goes through `get_store()`, which returns either `MongoStore`
   or `SQLiteStore`. Both are tested against the same suite of
   integration tests. An ABC would just duplicate that test coverage
   as type-checker noise.

4. **Future backends (Postgres, Redis) can still implement the
   Protocol.** They just won't be forced to inherit an ABC they don't
   need.

## Consequences

- `StorageInterface` is a `Protocol` (structural typing), not an `ABC`
  (nominal typing).
- `isinstance(store, StorageLike)` works at runtime (Protocol with
  `@runtime_checkable`).
- New backends must support the Motor collection-attribute pattern.
  If a future backend can't (e.g. a key-value store), it must expose
  a `__getattr__` that returns a collection-like adapter.
