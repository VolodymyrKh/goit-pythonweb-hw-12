"""Rate limiter shared by the application (slowapi, keyed by client IP)."""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
