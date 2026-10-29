# URL-ledger readers

`build` publishes one verified immutable generation and retires superseded derived generations under the exclusive `.build.lock`. Original browser captures and authored resolution state have separate owners.

Readers that need a generation to remain available run their bounded read under the same owner lock:

```sh
sinnix-url-ledger published --derived-root <derived-root> --exec <reader-command> <args...>
```

The command receives `SINNIX_URL_LEDGER_GENERATION`. The owner takes a shared lock before verifying and selecting the generation, shares its kernel lease with the child, and releases it when the reader processes close. Reader exit status propagates. Plain `published` prints a verified path for inspection; it provides no lifetime lease.

`sinnix-video-resolve` uses this wrapper only through DuckDB extraction. Downloads run after extraction has closed, allowing a waiting publisher to commit and reclaim the predecessor. `SINNIX_URL_LEDGER_PARQUET` explicitly selects a caller-owned file; its caller supplies the lifetime guarantee.
