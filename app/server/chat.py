import uuid

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.server.llm import LLMAgent

from langchain_mcp_adapters.client import MultiServerMCPClient
import os
from langfuse.callback import CallbackHandler


chat_router = APIRouter()


class ChatRequest(BaseModel):
    message: str


def get_user_chat_config(session_id: str) -> dict:
    langfuse_handler = CallbackHandler(
            user_id="TestAirflowMCP",
            session_id=f"{session_id}",
            public_key="pk-lf-6dabfdb8-8f1b-448e-91ce-843757a22d13",
            secret_key="sk-lf-ce3e5fea-fb42-4085-afba-4cbda68b54ca",
            host="http://host.docker.internal:3000"
        )
    return {'configurable': {'thread_id': session_id},
            "recursion_limit": 100,
            "callbacks": [langfuse_handler]
            }


@chat_router.post("/new")
async def new_chat(request: Request):
    """Create a new chat session."""
    request.session['chat_session_id'] = f'user_{uuid.uuid4()}'
    return {'results': 'ok'}


@chat_router.post("/ask")
async def chat(
    request: Request,
    chat_request: ChatRequest,
):
    if 'chat_session_id' not in request.session:
        await new_chat(request)
    session_id = request.session['chat_session_id']
    # Get the user chat configuration and the LLM agent.
    user_config = get_user_chat_config(session_id)
    # mcps = {
    #             "AirflowMCP":
    #             {
    #                 'command': "python",
    #                 'args': ["/code/app/mcp_servers/mcp_airflow.py"],
    #                 "transport": "stdio",
    #             }
    #         }
    mcps = {
                "AirflowMCP": {
                    "url": "http://mcp_sse_server:8000/sse",
                    "transport": "sse",
                    "headers": {"Authorization": f"""Bearer {
                        os.environ.get('MCP_TOKEN')}"""}
                }
            }

    client = MultiServerMCPClient(mcps)
    tools = await client.get_tools()

    async def stream_agent_response():
        async with LLMAgent(tools=tools) as llm_agent:
            async for chat_msg in llm_agent.astream_events(
                 chat_request.message, user_config):
                yield chat_msg.content

    # Return the agent's response as a stream of JSON objects.
    return StreamingResponse(stream_agent_response(),
                             media_type='application/json')

# "mcp_server": {
#     "url": "http://mcp_sse_server:8000/sse",
#     "transport": "sse"
# }

