from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


DEFAULT_TUSHARE_HTTP_URL = "http://118.89.66.41:8010/"


@dataclass(frozen=True)
class TushareSettings:
    token: str
    http_url: str = DEFAULT_TUSHARE_HTTP_URL


def settings_from_config(config: dict[str, Any]) -> TushareSettings:
    provider_config = dict(config.get("providers", {}).get("tushare", {}) or {})
    token = (
        str(provider_config.get("token") or "").strip()
        or str(config.get("tushare_token") or "").strip()
        or os.getenv("TUSHARE_TOKEN", "").strip()
    )
    if not token:
        raise ValueError("Tushare token is required in providers.tushare.token or TUSHARE_TOKEN")

    http_url = (
        str(provider_config.get("http_url") or "").strip()
        or str(config.get("tushare_http_url") or "").strip()
        or os.getenv("TUSHARE_HTTP_URL", "").strip()
        or DEFAULT_TUSHARE_HTTP_URL
    )
    return TushareSettings(token=token, http_url=http_url)


def create_pro_api(settings: TushareSettings, *, ts_module: Any | None = None) -> Any:
    if ts_module is None:
        import tushare as ts_module

    pro = ts_module.pro_api(settings.token)
    pro._DataApi__http_url = settings.http_url
    return pro


def create_pro_api_from_config(config: dict[str, Any], *, ts_module: Any | None = None) -> Any:
    return create_pro_api(settings_from_config(config), ts_module=ts_module)
