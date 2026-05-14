"""W2-T07: Feishu adapter hot-path send/reply must use the async httpx
transport (FeishuAsyncTransport), not the blocking SDK + asyncio.to_thread.
"""

from __future__ import annotations

import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

try:
    import lark_oapi  # noqa: F401

    _HAS_LARK_OAPI = True
except ImportError:
    _HAS_LARK_OAPI = False

try:
    import httpx  # noqa: F401

    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False


pytestmark = pytest.mark.skipif(
    not (_HAS_LARK_OAPI and _HAS_HTTPX),
    reason="lark_oapi and httpx required for the Feishu async transport tests",
)


def _make_skeleton_adapter():
    """A minimal FeishuAdapter shell — bypasses __init__ to avoid the
    full settings/config dance.  The thread-routing tests in
    test_stream_consumer_thread_routing.py use the same pattern.
    """
    from gateway.platforms.feishu import FeishuAdapter

    adapter = MagicMock(spec=FeishuAdapter)
    return adapter


def _make_httpx_response(payload: dict, status: int = 200):
    """Build a Mock standing in for httpx.Response with a .json() method."""
    resp = MagicMock()
    resp.status_code = status
    resp.json = MagicMock(return_value=payload)
    resp.text = json.dumps(payload)
    return resp


class TestFeishuSendUsesAsyncHttpx(unittest.IsolatedAsyncioTestCase):
    async def test_send_routes_create_through_async_transport(self):
        """A non-reply, non-thread send hits send_message with the right
        JSON body and the SDK message.create is NEVER touched."""
        from gateway.platforms._feishu_async import FeishuAsyncTransport
        from gateway.platforms.feishu import FeishuAdapter

        adapter = _make_skeleton_adapter()
        # Wire the SDK client to a magic mock so any accidental call
        # would still register loud enough to surface in assertions.
        sdk_client = MagicMock()
        adapter._client = sdk_client

        transport = MagicMock(spec=FeishuAsyncTransport)
        transport.send_message = AsyncMock(
            return_value=SimpleNamespace(
                code=0,
                msg="ok",
                data=SimpleNamespace(message_id="om_via_async"),
                success=lambda: True,
            )
        )
        transport.reply_message = AsyncMock()
        adapter._async_transport = transport

        result = await FeishuAdapter._send_raw_message(
            adapter,
            chat_id="oc_main_chat",
            msg_type="text",
            payload=json.dumps({"text": "hello"}),
            reply_to=None,
            metadata=None,
        )

        # Hot-path landed on the async transport, NOT the SDK.
        transport.send_message.assert_awaited_once()
        transport.reply_message.assert_not_called()
        sdk_client.im.v1.message.create.assert_not_called()
        sdk_client.im.v1.message.reply.assert_not_called()

        # Right body shape: receive_id is the chat_id, receive_id_type
        # resolves to chat_id (not open_id, not thread_id).
        kwargs = transport.send_message.await_args.kwargs
        self.assertEqual(kwargs["receive_id"], "oc_main_chat")
        self.assertEqual(kwargs["receive_id_type"], "chat_id")
        self.assertEqual(kwargs["msg_type"], "text")
        self.assertEqual(json.loads(kwargs["content"])["text"], "hello")
        self.assertIn("uuid_value", kwargs)

        # And we returned the transport's response object verbatim.
        self.assertEqual(result.data.message_id, "om_via_async")

    async def test_reply_routes_through_async_transport(self):
        """A send with reply_to set hits reply_message; SDK reply is
        never called."""
        from gateway.platforms._feishu_async import FeishuAsyncTransport
        from gateway.platforms.feishu import FeishuAdapter

        adapter = _make_skeleton_adapter()
        adapter._client = MagicMock()

        transport = MagicMock(spec=FeishuAsyncTransport)
        transport.reply_message = AsyncMock(
            return_value=SimpleNamespace(
                code=0,
                msg="ok",
                data=SimpleNamespace(message_id="om_replied"),
                success=lambda: True,
            )
        )
        transport.send_message = AsyncMock()
        adapter._async_transport = transport

        result = await FeishuAdapter._send_raw_message(
            adapter,
            chat_id="oc_main_chat",
            msg_type="text",
            payload=json.dumps({"text": "reply"}),
            reply_to="om_parent",
            metadata={"thread_id": "omt_topic"},
        )

        transport.reply_message.assert_awaited_once()
        transport.send_message.assert_not_called()
        adapter._client.im.v1.message.reply.assert_not_called()

        kwargs = transport.reply_message.await_args.kwargs
        self.assertEqual(kwargs["message_id"], "om_parent")
        self.assertEqual(kwargs["msg_type"], "text")
        # Thread_id metadata flips reply_in_thread on.
        self.assertTrue(kwargs["reply_in_thread"])
        self.assertEqual(result.data.message_id, "om_replied")

    async def test_transport_send_message_posts_to_correct_endpoint(self):
        """The transport itself, when its httpx.AsyncClient is mocked,
        POSTs to /open-apis/im/v1/messages with the right JSON body and
        a Bearer token.
        """
        from gateway.platforms._feishu_async import FeishuAsyncTransport

        # Build a real SDK client to exercise FeishuAsyncTransport
        # against the real ``_config``.
        import lark_oapi as lark
        from lark_oapi.core.const import FEISHU_DOMAIN

        sdk_client = (
            lark.Client.builder()
            .app_id("cli_unit_test")
            .app_secret("secret_unit_test")
            .domain(FEISHU_DOMAIN)
            .build()
        )
        transport = FeishuAsyncTransport(sdk_client=sdk_client)

        # Stub the token fetch so we don't hit the network or the
        # real TokenManager cache.
        transport._tenant_token = AsyncMock(return_value="t-cached-token")

        # Stub the httpx client.
        mock_response = _make_httpx_response(
            {"code": 0, "msg": "ok", "data": {"message_id": "om_new"}}
        )
        mock_async_client = MagicMock()
        mock_async_client.post = AsyncMock(return_value=mock_response)
        transport._client = mock_async_client  # bypass lazy build

        result = await transport.send_message(
            receive_id_type="chat_id",
            receive_id="oc_main_chat",
            msg_type="text",
            content=json.dumps({"text": "hi"}),
            uuid_value="uuid-1",
        )

        mock_async_client.post.assert_awaited_once()
        call_args = mock_async_client.post.await_args
        # Endpoint path
        self.assertEqual(call_args.args[0], "/open-apis/im/v1/messages")
        # Query string
        self.assertEqual(
            call_args.kwargs["params"], {"receive_id_type": "chat_id"}
        )
        # Body fields
        body = call_args.kwargs["json"]
        self.assertEqual(body["receive_id"], "oc_main_chat")
        self.assertEqual(body["msg_type"], "text")
        self.assertEqual(body["uuid"], "uuid-1")
        self.assertEqual(json.loads(body["content"])["text"], "hi")
        # Auth header
        self.assertEqual(
            call_args.kwargs["headers"]["Authorization"],
            "Bearer t-cached-token",
        )
        # Response surfaces the SDK shape
        self.assertTrue(result.success())
        self.assertEqual(result.data.message_id, "om_new")

    async def test_transport_reply_message_uses_path_template(self):
        """reply_message must inject message_id into the path template."""
        from gateway.platforms._feishu_async import FeishuAsyncTransport

        import lark_oapi as lark
        from lark_oapi.core.const import FEISHU_DOMAIN

        sdk_client = (
            lark.Client.builder()
            .app_id("cli_unit_test")
            .app_secret("secret_unit_test")
            .domain(FEISHU_DOMAIN)
            .build()
        )
        transport = FeishuAsyncTransport(sdk_client=sdk_client)
        transport._tenant_token = AsyncMock(return_value="t-cached-token")

        mock_response = _make_httpx_response(
            {"code": 0, "msg": "ok", "data": {"message_id": "om_replied"}}
        )
        mock_async_client = MagicMock()
        mock_async_client.post = AsyncMock(return_value=mock_response)
        transport._client = mock_async_client

        await transport.reply_message(
            message_id="om_parent_xyz",
            msg_type="text",
            content=json.dumps({"text": "thread"}),
            reply_in_thread=True,
            uuid_value="uuid-2",
        )

        mock_async_client.post.assert_awaited_once()
        call_args = mock_async_client.post.await_args
        self.assertEqual(
            call_args.args[0],
            "/open-apis/im/v1/messages/om_parent_xyz/reply",
        )
        body = call_args.kwargs["json"]
        self.assertTrue(body["reply_in_thread"])
        self.assertEqual(body["uuid"], "uuid-2")

    async def test_transport_aclose_closes_http_client(self):
        """aclose() must close any lazily-built httpx.AsyncClient and
        is safe to call when one was never built.
        """
        from gateway.platforms._feishu_async import FeishuAsyncTransport

        import lark_oapi as lark
        from lark_oapi.core.const import FEISHU_DOMAIN

        sdk_client = (
            lark.Client.builder()
            .app_id("cli_unit_test")
            .app_secret("secret_unit_test")
            .domain(FEISHU_DOMAIN)
            .build()
        )
        transport = FeishuAsyncTransport(sdk_client=sdk_client)

        # Case 1: client never built — aclose is a no-op.
        await transport.aclose()
        self.assertIsNone(transport._client)

        # Case 2: client built — aclose closes it.
        mock_client = MagicMock()
        mock_client.aclose = AsyncMock()
        transport._client = mock_client
        await transport.aclose()
        mock_client.aclose.assert_awaited_once()
        self.assertIsNone(transport._client)


if __name__ == "__main__":
    unittest.main()
