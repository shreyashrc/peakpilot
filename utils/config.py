import os
from typing import List


def get_source_order() -> List[str]:
    order = os.getenv("SOURCE_ORDER", "indiahikes,web").strip()
    return [s.strip().lower() for s in order.split(",") if s.strip()]


def is_enabled(source: str) -> bool:
    key = f"ENABLE_{source.upper()}"
    default = "true" if source in {"indiahikes", "web"} else "false"
    val = os.getenv(key, default).strip().lower()
    return val in {"1", "true", "yes", "on"}

