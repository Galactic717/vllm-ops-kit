# Disk pressure

1. Inspect node DiskPressure, pod events and PVC usage. Use df -h and df -i on the affected filesystem. Check whether model caches, PostgreSQL data, Redis append-only files or logs grew.
2. Archive or rotate logs and remove only expired artifacts you can recreate. Expand storage if the StorageClass supports it. Coordinate database or Redis maintenance with the data owner and preserve recoverable backups.
3. Confirm node conditions clear, PVC writes succeed and probes return healthy. Record the growing directory, remaining space and cleanup scope.
