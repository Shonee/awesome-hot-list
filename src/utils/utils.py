# -*- coding: utf-8 -*-
"""Small environment and secret helpers used by the collection CLI."""

import logging
import os


logger = logging.getLogger(__name__)
DOTENV_CANDIDATES = (".env", "src/script/.env")


def load_dotenv(path: str = None, override: bool = False) -> int:
    """Load simple ``KEY=VALUE`` entries without adding a dotenv dependency."""
    candidates = [path] if path else list(DOTENV_CANDIDATES)
    loaded = 0
    for candidate in candidates:
        if not candidate or not os.path.isfile(candidate):
            continue
        with open(candidate, "r", encoding="utf-8") as file:
            for raw_line in file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and (override or key not in os.environ):
                    os.environ[key] = value
                    loaded += 1
        logger.debug("已加载配置: %s（%d 项）", candidate, loaded)
        break
    return loaded
