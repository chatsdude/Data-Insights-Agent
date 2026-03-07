from __future__ import annotations

import os
import uuid


APP_SCOPE = os.environ.get("KNOWLEDGE_APP_SCOPE", "text2sql")
# Stable defaults for local testing. Override in .env when needed.
CURRENT_SESSION_ID = os.environ.get(
    "KNOWLEDGE_SESSION_ID",
    "bf222636-5e6e-4bac-9930-e3ae509567dd",
)
DEFAULT_SPACE_ID = os.environ.get(
    "KNOWLEDGE_DEFAULT_SPACE_ID",
    "f10241dc-4852-4f7c-8058-27fd368805c8",
)
