import httpx

from support_bot.chatwoot import ChatwootClient


async def test_conversation_lookup_gets_the_conversation_as_the_bot():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, request.headers.get("api_access_token")))
        return httpx.Response(200, json={"id": 9, "status": "pending", "meta": {}})

    client = ChatwootClient("http://chatwoot", "bot-token")
    client.client = httpx.AsyncClient(base_url="http://chatwoot", headers={"api_access_token": "bot-token"}, transport=httpx.MockTransport(handler))
    assert (await client.conversation(1, 9))["status"] == "pending"
    assert seen == [("GET", "/api/v1/accounts/1/conversations/9", "bot-token")]
