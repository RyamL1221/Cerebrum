import contextlib
import contextvars

from pydantic import BaseModel, Field
from typing_extensions import Literal

import requests
from typing import Dict, Any, Iterator, List, Optional

from cerebrum.config.config_manager import config

aios_kernel_url = config.get_kernel_url()

class Query(BaseModel):
    """
    Base class for all query types in the AIOS system.
    
    This class serves as the foundation for specialized query classes like LLMQuery,
    MemoryQuery, StorageQuery, and ToolQuery. It defines the minimum structure required
    for a valid query within the AIOS ecosystem.
    
    Attributes:
        query_class: Identifier for the query type, must be one of 
                     ["llm", "memory", "storage", "tool"]
    """
    query_class: Literal["llm", "memory", "storage", "tool"]
    
class Response(BaseModel):
    """
    Base class for all response types in the AIOS system.
    
    This class serves as the foundation for specialized response classes like LLMResponse,
    MemoryResponse, StorageResponse, and ToolResponse. It defines the minimum structure
    required for a valid response within the AIOS ecosystem.
    
    Attributes:
        response_class: Identifier for the response type, must be one of 
                        ["llm", "memory", "storage", "tool"]
    """
    response_class: Literal["llm", "memory", "storage", "tool"]

def post(base_url: str, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send a POST request to the specified API endpoint.
    
    Args:
        base_url: Base URL of the API server
        endpoint: API endpoint path
        data: JSON-serializable dictionary to be sent in the request body
        
    Returns:
        Parsed JSON response as a dictionary
        
    Raises:
        requests.exceptions.HTTPError: If the request fails
    """
    response = requests.post(f"{base_url}{endpoint}", json=data)
    response.raise_for_status()
    return response.json()

# The kernel session the current agent turn runs in (AIOS
# docs/STRESS_DIMENSIONS.md, "wrong_user"): set by the deployment around
# the agents' runs, never by an agent's own code. A context variable, so
# a thread or task started in a copy of the context carries it.
_KERNEL_SESSION: contextvars.ContextVar = contextvars.ContextVar(
    "aios_kernel_session", default=None
)


def current_kernel_session() -> Optional[str]:
    """The token of the kernel session in force, or None."""
    return _KERNEL_SESSION.get()


@contextlib.contextmanager
def kernel_session(session_token: Optional[str]) -> Iterator[None]:
    """Run the block in the kernel session ``session_token`` (None: no
    session): every request ``send_request`` sends carries it, and the
    kernel binds the request to the session's user."""
    reset = _KERNEL_SESSION.set(session_token)
    try:
        yield
    finally:
        _KERNEL_SESSION.reset(reset)


def open_kernel_session(user_id: str,
                        base_url: str = aios_kernel_url) -> str:
    """Open a kernel session for ``user_id`` (``POST /session/open``);
    its token."""
    return post(base_url, "/session/open", {"user_id": user_id})[
        "session_token"]


def close_kernel_session(session_token: str,
                         base_url: str = aios_kernel_url) -> bool:
    """End a kernel session (``POST /session/close``)."""
    return bool(post(base_url, "/session/close",
                     {"session_token": session_token}).get("closed"))


def send_request(agent_name: str, query: Query, base_url: str = aios_kernel_url):
    """
    Send a query to the AIOS kernel on behalf of an agent.
    
    Args:
        agent_name: Name of the agent making the request
        query: Query object containing the request details
        base_url: Base URL of the AIOS kernel
        
    Returns:
        Parsed JSON response from the AIOS kernel
    """
    query_type = query.query_class
    body = {
        'query_type': query_type,
        'agent_name': agent_name,
        'query_data': query.model_dump()}
    # A request sent inside ``kernel_session`` carries its token.
    session_token = current_kernel_session()
    if session_token:
        body['session_token'] = session_token
    result = post(base_url, "/query", body)

    return result
