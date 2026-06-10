# Solution Steps

1. Add a resilient Redis access layer so Redis failures never break request handling. Keep a lazy singleton client, but catch redis.exceptions.RedisError anywhere Redis is read or written, and expose a lightweight availability check for health status.

2. Make the in-memory data the source-of-truth fallback. Keep shipping rates in the existing in-process list, and replace the static zone-default lookup with a mutable in-memory zone config store so admin pricing updates still work even when Redis is down.

3. Standardize all Redis keys with one namespace and a consistent colon-separated format, such as logistics:rate:..., logistics:zone:{zone_id}:config, and logistics:quote:... . Avoid mixing -, _, and : in key names.

4. Store each zone configuration as a single serialized JSON value under one Redis key instead of splitting it across multiple keys. This reduces zone lookups from several Redis round-trips to a single GET while keeping the payload self-contained.

5. Introduce quote-cache TTLs so cached quotes expire predictably. Use a short, explicit TTL such as 300 seconds for quote responses to prevent indefinite staleness.

6. Fix quote invalidation by versioning zone configs. Add a version field to the internal ZoneConfig model, increment it whenever zone pricing is updated, and include that version in the quote cache key. This makes new quotes immediately bypass stale cached entries after a pricing change.

7. Update the zone-pricing admin path so it always writes to the in-memory zone database first, then best-effort writes the refreshed zone config to Redis. If Redis is unavailable, the API should still succeed and future quote requests should read the updated DB-backed config.

8. Change quote generation to normalize inputs, load the shipping rate from the in-memory database, load zone config from Redis with DB fallback, then read/write the quote cache using the versioned quote key. All Redis interactions should be wrapped in safe try/except blocks.

9. Warm Redis on startup using best-effort seeding with a pipeline so multiple reference keys are written in a single batch. Startup must not fail if Redis is unreachable.

10. Keep the HTTP surface the same, but update health reporting to return an application-ok status even when Redis is degraded so operators can see dependency health without turning transient Redis problems into 500s.

