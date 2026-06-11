from __future__ import annotations

from typing import TypeAlias

UNSET = object()

# A value returned by sqlite3.Row
SqliteValue: TypeAlias = str | int | float | bytes | None

# Generic dict for DB row data
RowDict: TypeAlias = dict[str, SqliteValue]

# JSON-serializable dict used in API responses
JsonDict: TypeAlias = dict[str, object]
JsonList: TypeAlias = list[JsonDict]
