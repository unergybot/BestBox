# Database Performance Troubleshooting

## Slow Query Diagnosis

When users report slow application performance, database queries are often the culprit. Follow this systematic approach to identify and resolve issues.

### Step 1: Identify Slow Queries

**PostgreSQL:**
```sql
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 20;
```

**MySQL:**
```sql
SELECT * FROM sys.statement_analysis
ORDER BY avg_latency DESC
LIMIT 20;
```

Look for:
- Queries with execution time > 1 second
- High-frequency queries (>1000 calls/hour) with >100ms avg time
- Full table scans on large tables

### Step 2: Analyze Query Execution Plan

**PostgreSQL EXPLAIN:**
```sql
EXPLAIN (ANALYZE, BUFFERS) SELECT ...;
```

**MySQL EXPLAIN:**
```sql
EXPLAIN FORMAT=JSON SELECT ...;
```

Red flags in execution plans:
- Seq Scan on tables with >10,000 rows
- Nested loops with high row estimates
- Hash joins consuming excessive memory
- Sort operations spilling to disk

### Step 3: Review Missing Indexes

Check for columns frequently used in:
- WHERE clauses without indexes
- JOIN conditions on non-indexed foreign keys
- ORDER BY columns without supporting indexes

## Common Issues and Quick Fixes

**Issue: Missing Index on Foreign Key**
- Symptom: Slow JOIN queries, high table scan counts
- Fix: `CREATE INDEX idx_table_fk ON table(foreign_key_column);`

**Issue: Outdated Statistics**
- Symptom: Bad query plans, unexpected seq scans
- Fix (PostgreSQL): `ANALYZE table_name;`
- Fix (MySQL): `ANALYZE TABLE table_name;`

**Issue: Lock Contention**
- Symptom: Queries waiting, timeout errors
- Check (PostgreSQL): `SELECT * FROM pg_locks JOIN pg_stat_activity USING (pid);`
- Resolution: Identify blocking queries, optimize transaction scope

**Issue: Connection Pool Exhaustion**
- Symptom: "Too many connections" errors
- Fix: Review connection pool settings (max_connections, pool_size)
- Consider: Read replicas for read-heavy workloads

## Monitoring Best Practices

- Set up alerts for query execution time > 5 seconds
- Monitor connection pool utilization (alert at >80%)
- Track query cache hit ratio (target >90%)
- Review slow query logs daily
- Conduct monthly index optimization reviews

## Performance Tuning Parameters

**PostgreSQL:**
- `shared_buffers`: 25% of RAM for dedicated DB server
- `effective_cache_size`: 50-75% of RAM
- `work_mem`: 16-64MB per operation (tune based on workload)
- `maintenance_work_mem`: 1GB for large databases

**MySQL:**
- `innodb_buffer_pool_size`: 70-80% of RAM for InnoDB
- `query_cache_size`: 64-128MB (if query cache enabled)
- `max_connections`: Balance between concurrency and resource limits

## Escalation

Escalate to DBA team if:
- Query optimization doesn't improve performance after index creation
- Disk I/O consistently >80% (may need storage upgrade)
- CPU usage >90% during normal operations
- Considering table partitioning or sharding strategies
