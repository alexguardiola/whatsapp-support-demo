import asyncio

import httpx

from support_bot.llm import OpenAICompatLLM
from support_bot.uds_relay import serve


async def fake_openai(reader, writer):
    await reader.readuntil(b"\r\n\r\n")
    body = (
        b'{"choices":[{"message":{"content":"{\\"answer\\":\\"ok\\",\\"cited_chunk_ids\\":[],'
        b'\\"confidence\\":0.9,\\"intent\\":\\"faq\\"}"}}],"usage":{"total_tokens":7}}'
    )
    writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % len(body) + body)
    await writer.drain()
    writer.close()


async def test_relay_forwards_unix_socket_to_tcp(tmp_path):
    upstream = await asyncio.start_server(fake_openai, "127.0.0.1", 0)
    port = upstream.sockets[0].getsockname()[1]
    sock = str(tmp_path / "llm.sock")
    relay = await serve(sock, "127.0.0.1", port)
    try:
        llm = OpenAICompatLLM("http://llm/v1", "m", uds=sock, timeout=5)
        reply, tokens = await llm.complete([{"role": "user", "content": "x"}])
        assert (reply.answer, tokens) == ("ok", 7)
    finally:
        relay.close()
        upstream.close()


async def test_relay_closes_client_when_upstream_is_down(tmp_path):
    sock = str(tmp_path / "llm.sock")
    relay = await serve(sock, "127.0.0.1", 1)
    try:
        async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=sock), timeout=3) as c:
            try:
                await c.get("http://llm/v1/models")
                raised = False
            except httpx.HTTPError:
                raised = True
        assert raised
    finally:
        relay.close()
