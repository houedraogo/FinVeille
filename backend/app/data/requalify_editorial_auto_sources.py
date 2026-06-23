"""Relance la qualification premium des flux editoriaux collectes automatiquement."""

from __future__ import annotations

import asyncio
import json

from app.services.editorial_requalifier import requalify_editorial_auto_sources


def main() -> None:
    result = asyncio.run(requalify_editorial_auto_sources())
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
