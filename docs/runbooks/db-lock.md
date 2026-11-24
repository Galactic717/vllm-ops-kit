# PostgreSQL locks or connection pressure

1. Check the pool panel and client connection count. Sample waiting sessions using the approved PostgreSQL operator identity.

~~~sql
SELECT pid, wait_event_type, wait_event, pg_blocking_pids(pid) AS blockers,
       now() - xact_start AS transaction_age
FROM pg_stat_activity
WHERE datname = current_database() AND wait_event_type = 'Lock';
~~~

2. Identify the owner and operation behind a long blocker. Coordinate cancellation of its query with the owner before ending a session or rolling back transactions. If the pool is saturated, lower incoming concurrency and verify one controlled query before increasing capacity.
3. Check that blocked sessions clear, API readiness and workflow processing return, and connections stay within the database budget. Record the transaction age and query category.
