"""Async httpx-based fast path for the Feishu IM message endpoints.

Hot-path message sends used to call into the synchronous ``lark_oapi`` SDK
via ``asyncio.to_thread(self._client.im.v1.message.{reply,create}, ...)``,
which costs one threadpool worker per outbound message for the full
200–800 ms duration of the round-trip.  Under load that pins the default
``asyncio`` executor and starves unrelated I/O.

This helper sidesteps the SDK's blocking transport by:

1. Reusing the SDK's ``TokenManager`` cache to fetch the tenant access
   token (cached for ~2h, so the cache-miss path is rare).  When the
   cache is warm this is purely in-process and synchronous; the rare
   cache-miss path is dispatched through ``asyncio.to_thread`` so it
   doesn't block the event loop.
2. Issuing the actual ``POST`` over a per-adapter ``httpx.AsyncClient``
   so the wire request never blocks the loop.
3. Wrapping the JSON response in the SDK's response classes so callers
   can keep using ``response.success()``, ``response.data.message_id``,
   ``response.code``/``msg`` exactly as before.

Only the two highest-frequency endpoints are exposed:

* ``POST /open-apis/im/v1/messages``                                (create)
* ``POST /open-apis/im/v1/messages/{message_id}/reply``             (reply)

Other Feishu API calls remain on the SDK + ``asyncio.to_thread`` path —
they are far less hot and migrating them is out of scope for W2-T07.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

try:
    import httpx
except ImportError:  # pragma: no cover — optional dep
    httpx = None  # type: ignore[assignment]

try:
    from lark_oapi.api.im.v1 import CreateMessageResponse, ReplyMessageResponse
    from lark_oapi.core.token.manager import TokenManager

    _LARK_AVAILABLE = True
except ImportError:  # pragma: no cover — only fires when feishu extra not installed
    CreateMessageResponse = None  # type: ignore[assignment]
    ReplyMessageResponse = None  # type: ignore[assignment]
    TokenManager = None  # type: ignore[assignment]
    _LARK_AVAILABLE = False

from gateway.platforms._http_client_limits import platform_httpx_limits


logger = logging.getLogger(__name__)


_DEFAULT_CONNECT_TIMEOUT_S = 5.0
_DEFAULT_READ_TIMEOUT_S = 15.0


class FeishuAsyncTransport:
    """Per-adapter async HTTP transport for Feishu message sends.

    Holds a lazy ``httpx.AsyncClient`` keyed to the adapter's domain.
    The client is created on first call and torn down via
    :meth:`aclose`, which the adapter invokes from its ``disconnect``
    path.
    """

    def __init__(self, *, sdk_client: Any) -> None:
        """Create a transport bound to a built ``lark_oapi`` client.

        The SDK client is the authoritative source for ``app_id``,
        ``app_secret``, ``domain``, and the shared
        ``TokenManager`` cache — we never duplicate any of that state
        here.
        """
        if not _LARK_AVAILABLE:
            raise RuntimeError(
                "lark_oapi is not available; cannot use FeishuAsyncTransport"
            )
        if httpx is None:
            raise RuntimeError(
                "httpx is not available; cannot use FeishuAsyncTransport"
            )
        if sdk_client is None:
            raise ValueError("sdk_client must be a built lark_oapi.Client")
        # The SDK stashes its Config (app_id/secret/domain/cache) on _config.
        config = getattr(sdk_client, "_config", None)
        if config is None:
            raise ValueError(
                "sdk_client._config is None; pass a fully-built lark_oapi.Client"
            )
        self._config = config
        self._client: Optional["httpx.AsyncClient"] = None
        self._client_lock = asyncio.Lock()

    @property
    def base_url(self) -> str:
        return str(self._config.domain).rstrip("/")

    async def _get_client(self) -> "httpx.AsyncClient":
        """Lazily build the AsyncClient on first use."""
        if self._client is not None:
            return self._client
        async with self._client_lock:
            if self._client is not None:  # double-checked under lock
                return self._client
            limits = platform_httpx_limits()
            timeout = httpx.Timeout(
                connect=_DEFAULT_CONNECT_TIMEOUT_S,
                read=_DEFAULT_READ_TIMEOUT_S,
                write=_DEFAULT_READ_TIMEOUT_S,
                pool=_DEFAULT_CONNECT_TIMEOUT_S,
            )
            kwargs: dict[str, Any] = {
                "base_url": self.base_url,
                "timeout": timeout,
                "http2": False,
            }
            if limits is not None:
                kwargs["limits"] = limits
            self._client = httpx.AsyncClient(**kwargs)
            return self._client

    async def aclose(self) -> None:
        """Close the underlying AsyncClient if one was lazily built."""
        client = self._client
        self._client = None
        if client is not None:
            try:
                await client.aclose()
            except Exception as exc:  # pragma: no cover — defensive
                logger.debug(
                    "[Feishu async] aclose error: %s", exc, exc_info=True
                )

    async def _tenant_token(self) -> str:
        """Fetch the cached tenant access token from the SDK's TokenManager.

        99.9% of the time this is an O(1) in-memory cache hit; only on
        the rare miss (every ~2 hours per app, on token expiry) does the
        SDK perform a blocking HTTP request.  Wrap in ``to_thread`` so
        that miss doesn't pause the event loop.
        """
        return await asyncio.to_thread(
            TokenManager.get_self_tenant_token, self._config
        )

    async def send_message(
        self,
        *,
        receive_id_type: str,
        receive_id: str,
        msg_type: str,
        content: str,
        uuid_value: Optional[str] = None,
    ) -> Any:
        """POST /open-apis/im/v1/messages — returns a ``CreateMessageResponse``.

        Mirrors the SDK's ``client.im.v1.message.create`` response shape
        so existing call-sites can stay on ``response.success()`` /
        ``response.data.message_id`` without changes.
        """
        token = await self._tenant_token()
        body: dict[str, Any] = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": content,
        }
        if uuid_value:
            body["uuid"] = uuid_value
        client = await self._get_client()
        resp = await client.post(
            "/open-apis/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            json=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
        )
        return self._wrap_response(resp, CreateMessageResponse)

    async def reply_message(
        self,
        *,
        message_id: str,
        msg_type: str,
        content: str,
        reply_in_thread: bool,
        uuid_value: Optional[str] = None,
    ) -> Any:
        """POST /open-apis/im/v1/messages/{message_id}/reply.

        Returns a ``ReplyMessageResponse`` matching the SDK shape.
        """
        token = await self._tenant_token()
        body: dict[str, Any] = {
            "content": content,
            "msg_type": msg_type,
            "reply_in_thread": reply_in_thread,
        }
        if uuid_value:
            body["uuid"] = uuid_value
        client = await self._get_client()
        # message_id goes in the path — quote defensively even though
        # om_xxx ids are url-safe.
        from urllib.parse import quote

        path = f"/open-apis/im/v1/messages/{quote(str(message_id), safe='')}/reply"
        resp = await client.post(
            path,
            json=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
        )
        return self._wrap_response(resp, ReplyMessageResponse)

    @staticmethod
    def _wrap_response(http_resp: "httpx.Response", response_cls: Any) -> Any:
        """Inflate the SDK response dataclass from an httpx response.

        On HTTP transport-level errors (non-2xx with no JSON body) we
        synthesise a minimal response that ``BaseResponse.success()``
        will treat as a failure, mirroring how the SDK surfaces network
        errors.
        """
        try:
            payload = http_resp.json()
        except Exception:  # JSON-decoding failure
            payload = {
                "code": -1,
                "msg": (
                    f"feishu http {http_resp.status_code}: "
                    f"{http_resp.text[:200]!r}"
                ),
            }
        # response_cls.__init__(d) populates code/msg/data via construct.init.
        return response_cls(payload)
