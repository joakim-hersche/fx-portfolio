"""TTL caches for data-fetch functions.

Three separate caches prevent key collisions between
history, fundamentals, and name lookups.
"""

import hashlib
import json
import logging

from cachetools import TTLCache, cached
from cachetools.keys import hashkey

_log = logging.getLogger(__name__)
_log.info("Cache cold start — all data will be fetched fresh from upstream APIs")

short_cache = TTLCache(maxsize=256, ttl=300)      # 5 min — live prices, FX rates
long_cache  = TTLCache(maxsize=256, ttl=86400)   # 24 hours — fundamentals, history

# Per-function long caches to avoid key collisions when different functions
# receive the same arguments (e.g. fetch_price_history_long("AAPL") vs
# fetch_company_name("AAPL") would collide in a shared cache).
long_cache_history = TTLCache(maxsize=256, ttl=86400)
long_cache_simulation = TTLCache(maxsize=256, ttl=86400)
long_cache_analytics = TTLCache(maxsize=256, ttl=86400)
long_cache_fundamentals = TTLCache(maxsize=256, ttl=86400)
long_cache_names = TTLCache(maxsize=256, ttl=86400)
long_cache_risk_free = TTLCache(maxsize=64, ttl=86400)
long_cache_splits = TTLCache(maxsize=256, ttl=86400)


def _make_hashable(obj):
    """Convert unhashable types (dict, list, DataFrame) to a hashable digest.

    Uses JSON serialisation instead of pickle to avoid RCE risk from
    deserialising untrusted data.
    """
    try:
        hash(obj)
        return obj
    except TypeError:
        # Use JSON for safe serialisation; fall back to repr for non-JSON types
        try:
            return hashlib.md5(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()
        except (TypeError, ValueError):
            return hashlib.md5(repr(obj).encode()).hexdigest()



def lenient_key(*args, **kwargs):
    """Cache key function that handles unhashable arguments like dicts and DataFrames."""
    args = tuple(_make_hashable(a) for a in args)
    kwargs = {k: _make_hashable(v) for k, v in kwargs.items()}
    return hashkey(*args, **kwargs)
