#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

DEFAULT_TIMEOUT = 10


class ResolverError(RuntimeError):
    pass


def _load_ctx_from_stdin() -> dict[str, Any]:
    try:
        raw = sys.stdin.buffer.read()
        if not raw:
            raise ValueError("stdin is empty")
        ctx = json.loads(raw)
        if not isinstance(ctx, dict):
            raise ValueError("stdin JSON must be an object")
        return ctx
    except Exception as e:
        raise ResolverError(f"Invalid stdin JSON: {e}") from e


def _extract_source_url(ctx: dict[str, Any]) -> str:
    return str(ctx.get("source_url") or "").strip()


def _extract_channel_id(ctx: dict[str, Any]) -> str:
    source = _extract_source_url(ctx)
    if not source:
        return ""

    # 兼容 source_url = "...?id=099"
    try:
        parsed = urllib.parse.urlsplit(source)
        qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        qid = str(qs.get("id", [""])[0]).strip()
        if qid:
            return qid
    except Exception:
        pass

    # 兼容 nowtv://332 / viutv://096
    if source.startswith("nowtv://"):
        return source.removeprefix("nowtv://").strip("/").strip()
    if source.startswith("viutv://"):
        return source.removeprefix("viutv://").strip("/").strip()

    return ""


def _is_viutv_channel(channel_id: str) -> bool:
    return channel_id in {"099", "096"}


def _extract_user_agent(ctx: dict[str, Any]) -> str:
    extra = ctx.get("extra")
    if isinstance(extra, dict):
        ua = str(extra.get("user_agent") or "").strip()
        if ua:
            return ua

    ua = os.getenv("NOWTV_USER_AGENT", "").strip()
    if ua:
        return ua

    ua = os.getenv("USER_AGENT", "").strip()
    if ua:
        return ua

    return "Mozilla/5.0"


def _extract_socks5_proxy(ctx: dict[str, Any]) -> str:
    extra = ctx.get("extra")
    if isinstance(extra, dict):
        for key in ("socks5_proxy", "SOCKS5_PROXY"):
            val = str(extra.get(key) or "").strip()
            if val:
                return val

    val = os.getenv("SOCKS5_PROXY", "").strip()
    if val:
        return val

    return ""


def _install_socks5_proxy_if_needed(proxy: str) -> None:
    if not proxy:
        return

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)

    try:
        import _socks5  # noqa: E402
    except Exception as e:
        raise ResolverError(f"Failed to import _socks5 helper: {e}") from e

    _socks5.install(proxy)


def _fetch_api(url: str, channel_no: str, user_agent: str) -> dict[str, Any]:
    """
    通用请求逻辑，ViuTV 和 NOW TV 的接口参数格式是一样的，仅 URL 不同。
    """
    # 生成香港时间戳 (UTC+8) yyyyMMddHHmmss
    hk_tz = timezone(timedelta(hours=8))
    caller_ref = datetime.now(hk_tz).strftime("%Y%m%d%H%M%S")

    payload = {
        "callerReferenceNo": caller_ref,
        "contentId": channel_no,
        "contentType": "Channel",
        "channelno": channel_no,
        "mode": "prod",
        "deviceId": "808ae5d61057a504e7",
        "deviceType": "ANDROID_WEB"
    }

    data = json.dumps(payload).encode("utf-8")
    
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": user_agent,
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            res_body = resp.read()
            return json.loads(res_body)
    except Exception as e:
        raise ResolverError(f"Request to API failed: {e}") from e


def _call_viutv_api(channel_no: str, user_agent: str) -> dict[str, Any]:
    """
    ViuTV 获取逻辑
    """
    url = "https://api.viu.now.com/p8/3/getLiveURL"
    return _fetch_api(url, channel_no, user_agent)


def _call_nowtv_api(channel_no: str, user_agent: str) -> dict[str, Any]:
    """
    NOW TV 获取逻辑
    """
    url = "https://webtvapi.now.com/10/7/getLiveURL"
    return _fetch_api(url, channel_no, user_agent)


def _extract_asset_url(resp: dict[str, Any]) -> str:
    asset = resp.get("asset", "")
    if isinstance(asset, list):
        return str(asset[0] if asset else "").strip()
    return str(asset or "").strip()


def _extract_mpd_and_extra(platform: str, resp: dict[str, Any]) -> tuple[str, str, str, str, str]:
    mpd_url = _extract_asset_url(resp)
    drm_token = str(resp.get("drmToken", "") or "").strip()

    if platform == "viutv":
        license_server = "https://example.invalid/license"
        origin = "https://viu.tv"
        referer = "https://viu.tv/"
    else:
        license_server = "https://example.invalid/license"
        origin = "https://nowplayer.now.com"
        referer = "https://nowplayer.now.com/"

    return mpd_url, drm_token, license_server, origin, referer


async def resolve(ctx: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(ctx, dict):
        raise ResolverError("ctx must be a dict")

    channel_no = _extract_channel_id(ctx)
    if not channel_no:
        return ctx

    platform = "viutv" if _is_viutv_channel(channel_no) else "nowtv"
    print(f"platform={platform} channel_no={channel_no}", file=sys.stderr)

    user_agent = _extract_user_agent(ctx)
    proxy = _extract_socks5_proxy(ctx)
    _install_socks5_proxy_if_needed(proxy)

    if platform == "viutv":
        resp = await asyncio.to_thread(_call_viutv_api, channel_no, user_agent)
    else:
        resp = await asyncio.to_thread(_call_nowtv_api, channel_no, user_agent)

    if isinstance(resp, dict) and resp.get("responseCode") not in (None, "SUCCESS"):
        raise ResolverError(f"NOW TV API error: {resp.get('responseCode', 'unknown')}")

    mpd_url, drm_token, license_server, origin, referer = _extract_mpd_and_extra(platform, resp)
    if not mpd_url:
        raise ResolverError("API returned no MPD URL")

    print(f"mpd_url={mpd_url[:80]}...", file=sys.stderr)
    print(f"drm_token={'(set)' if drm_token else '(empty)'}", file=sys.stderr)

    extra = ctx.get("extra")
    if not isinstance(extra, dict):
        extra = {}
        ctx["extra"] = extra

    ctx["source_url"] = mpd_url
    if drm_token:
        extra["drm_token"] = drm_token
    extra["license_server"] = license_server
    extra["origin"] = origin
    extra["referer"] = referer

    return ctx


def main() -> None:
    try:
        ctx = _load_ctx_from_stdin()
        result = asyncio.run(resolve(ctx))
        json.dump(result, sys.stdout, ensure_ascii=False)
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()