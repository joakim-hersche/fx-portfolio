"""Framework-agnostic caching utilities.

Replaces @st.cache_data decorators with cachetools TTLCache so the data layer
has no Streamlit dependency.
"""

import hashlib
import pickle

from cachetools import TTLCache, cached
from cachetools.keys import hashkey

short_cache = TTLCache(maxsize=256, ttl=900)     # 15 min — live prices, FX rates
long_cache  = TTLCache(maxsize=256, ttl=86400)   # 24 hours — fundamentals, history


def _make_hashable(obj):
    """Convert unhashable types (dict, list, DataFrame) to a hashable digest."""
    try:
        hash(obj)
        return obj
    except TypeError:
        return hashlib.md5(pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)).hexdigest()


def lenient_key(*args, **kwargs):
    """Cache key function that handles unhashable arguments like dicts and DataFrames."""
    args = tuple(_make_hashable(a) for a in args)
    kwargs = {k: _make_hashable(v) for k, v in kwargs.items()}
    return hashkey(*args, **kwargs)
