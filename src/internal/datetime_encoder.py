"""datetimeをJSONに変換するためのエンコーダーを提供するモジュール."""

import datetime
import json


class DateTimeEncoder(json.JSONEncoder):
    """datetimeをJSONに変換するためのエンコーダー."""

    def default(self: "DateTimeEncoder", o: datetime.datetime | str) -> str:
        """datetimeをJSONに変換する."""
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        return super().default(o)
