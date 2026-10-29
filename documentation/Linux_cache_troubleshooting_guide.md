# Troubleshooting: High CPU & Memory Usage (Linux Cache Build-up)

## Context
In a single-node k3s cluster, there may be alerts for extremely high CPU and Memory usage. This is often not a real resource leak, but rather the Linux kernel caching disk operations.

## Symptoms
*   **High Memory Usage:** Standard monitoring tools or `top` report almost 100% RAM usage.
*   **High CPU Usage:** The CPU spikes heavily, usually driven by the `kswapd0` process (the kernel's memory management daemon).
*   **Diagnosis:** Running `free -h` reveals that the `used` memory is actually quite low, while the `buff/cache` column is consuming almost all available RAM.

## Root Cause
Large disk I/O operations (like database dumps, large file transfers, or bulk backups) cause the Linux kernel to fill up spare RAM with page cache, inodes, and dentries to speed up performance. When the RAM gets full, `kswapd0` works in overdrive to evict pages, which causes the CPU to spike. If left unchecked, this CPU spike can starve the k3s `kubelet`, potentially causing the node to drop into a `NotReady` state.

## Resolution
To immediately resolve this, manually force the Linux kernel to drop the caches. 

Run the following command as root or with `sudo`:

```bash
sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'
```

### What this command does:
1.  **`sync`**: Safely writes all pending, unsaved data (dirty pages) from memory to the physical disk. **Do not skip this step.**
2.  **`echo 3 > ...`**: Instructs the kernel to drop all clean pagecaches, dentries, and inodes. 

## Impact & Safety
*   **Completely Safe:** This command does not restart any k3s services, Kubernetes pods, or Gen3 microservices. It only drops "clean" caches. 
*   **Temporary Side Effect:** There may be a temporary dip in performance (an I/O spike) immediately after running the command. This is normal; your applications are just reading data directly from the physical disk while the kernel naturally rebuilds the cache over time.