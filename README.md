# CPU profiles for empty nullable column clones

ClickHouse parses each text value of a `LowCardinality(Nullable(String))` column into an empty clone of its dictionary's nested column. The null map in the clone has no rows. Constructing it with an explicit size of zero allocates 127 bytes of padding. The first appended null flag grows that buffer to 4096 bytes. Default construction lets the first append allocate the required buffer directly.

## Reproduce the workload

Run `python3 fixture.py` to generate `rows.ndjson` next to the script. It contains 400,000 rows with four fields, 64 recurring strings, empty strings and JSON nulls. Its SHA-256 is `673c3800f7259de65fd3eea8c9848e249c016957363e2e78e87ff163fb1249e8`.

```sql
CREATE TABLE sink
(
    a LowCardinality(Nullable(String)),
    b LowCardinality(Nullable(String)),
    c LowCardinality(Nullable(String)),
    d LowCardinality(Nullable(String))
)
ENGINE = Null
```

Send the file to each server with a single parser thread. For profiling, set `query_profiler_cpu_time_period_ns=2000000` and read CPU samples for the insert query IDs from `system.trace_log`.

```sh
curl --fail --silent --show-error \
  'http://localhost:8123/?max_threads=1&input_format_parallel_parsing=0&query=INSERT%20INTO%20sink%20FORMAT%20JSONEachRow' \
  --data-binary @rows.ndjson
```

## Matched builds

Both x86-64 builds use upstream commit `bdbd1b837b2b2368ccb351c68ace26e1806abc46` and Clang 21.1.8 with `-O1 -DNDEBUG`. They ran on the same Intel Xeon Gold 6148. The two executables differ only in the object compiled from `ColumnNullable.cpp`.

After three warm-ups per build, 15 inserts per build were timed through the loopback HTTP interface. The order of the two builds alternated each round. Elapsed time comes from `system.query_log.query_duration_ms`. CPU time is the sum of `UserTimeMicroseconds` and `SystemTimeMicroseconds` in the same log.

| Median per insert | Before | After |
|---|---:|---:|
| Elapsed | 1158 ms | 799 ms |
| CPU | 1157.7 ms | 798.9 ms |

Twelve additional inserts per build were CPU-profiled at 2 ms per sample. The [before](before.svg) and [after](after.svg) flame graphs start at the JSON row reader. Each graph scales its width to the samples in its own run. Compare the counts below to see how much CPU work disappeared for the same number of input rows.

| CPU samples | Before | After |
|---|---:|---:|
| JSON row reader | 6617 | 4920 |
| First null-map append inside low-cardinality deserialization | 1138 | 295 |
| Reallocation underneath that append | 1097 | 0 |

The narrower stack excludes character-buffer growth and dictionary insertion. The initial append still needs storage after the change. A separate insert into a `Memory` table produced the same 400,000 rows and the same `sum(cityHash64(tuple(a,b,c,d)))` of `2738923881975003103` on both builds. Column `a` contained 12,904 nulls and 22,770 empty strings.

The directory includes the original folded stacks, per-insert timings and sample counts. The PNG files are static previews of the SVGs.

## Official master build

The [official master CI profile](official-master.svg) uses commit `ec475edd5e3d658bda74c066db9d0244fa22edf1` and ten inserts of the same input. Its graph is rooted at native low-cardinality JSON deserialization. Of 4004 samples in that subtree, 764 reached the allocator's reallocation path through the nullable deserializer's first null-map append. The corresponding column, serializer and array implementations are identical at the PR base `0f20741543931a9e7fc5d8b5b689347eb5be2d5b`.

