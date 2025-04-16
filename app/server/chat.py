import uuid

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.server.llm import LLMAgent

from langchain_mcp_adapters.client import MultiServerMCPClient


chat_router = APIRouter()


class ChatRequest(BaseModel):
    message: str


def get_user_chat_config(session_id: str) -> dict:
    return {'configurable': {'thread_id': session_id},
            "recursion_limit": 100}


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
    print('sldnsfnlksdf')
    print(session_id)
    # Get the user chat configuration and the LLM agent.
    user_config = get_user_chat_config(session_id)

    async def stream_agent_response():
        """Stream the agent's response to the client."""
        mcps = {
                "AirflowMCP":
                {
                    'command': "python",
                    'args': ["/code/app/mcp_servers/mcp_airflow.py"],
                    "transport": "stdio",
                }
            }

        async with MultiServerMCPClient(mcps) as client:
            tools = client.get_tools()
            async with LLMAgent(tools=tools) as llm_agent:
                async for chat_msg in llm_agent.astream_events(
                   chat_request.message, user_config):
                    yield chat_msg.content

    # Return the agent's response as a stream of JSON objects.
    return StreamingResponse(stream_agent_response(),
                             media_type='application/json')
