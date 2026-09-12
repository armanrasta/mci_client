import httpx
import structlog
from enum import Enum
from tenacity import (retry,
                      retry_if_exception_type,
                      stop_after_attempt,
                      stop_after_delay,
                      wait_exponential)
from .models import NodeState, ApplyResult


logger = structlog.get_logger(__name__)


class HttpMethods(str, Enum):
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"


class Client:

    def __init__(self, timeout: float|int = 5, attempts: int = 5):
        self._client = httpx.AsyncClient(timeout=timeout)
        self._attempts = attempts
        # the retry is a decorator method, but as i wanted to use it with the configured values that get initiated in my client,
        # I prefered to make it an inside method to run it by a call in our functions.  
        self._retry = retry(
            stop=stop_after_attempt(self._attempts), #TODO: the delay and its failures need to get figured
            wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
            retry=retry_if_exception_type(
                (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError)
            ),
            reraise=True,
        )
    
    async def close(self):
        await self._client.aclose()
        logger.info("Client Closed")
        
    # Private Method
    async def _request(self, url: str, method:HttpMethods, json: dict | None = None) -> httpx.Response:
        return await self._retry(self._client.request)(method=method.value, url=url, json=json)
    
    async def get_state(self, host: str, group_id: str) -> NodeState:
        url = f"{host}/v1/group/{group_id}/"
        try:
            response = await self._request(url=url, method=HttpMethods.GET)
        except Exception as e:
            logger.warning(f"get_state failed: {e}\n")
            return NodeState.UNKNOWN
            
        match response.status_code:
            case 200:
                return NodeState.EXISTS
            case 404:
                return NodeState.ABSENT
            case _:
                return NodeState.UNKNOWN

    async def delete(self, host: str, group_id) -> ApplyResult:
        url = f"{host}/v1/group/"
        payload = {
               "groupId": group_id
              }
        
        try:
            response = await self._request(url=url, method=HttpMethods.DELETE, json=payload)
        except Exception as e:
            logger.warning("delete_failed", host=host, error=str(e))
            return ApplyResult(host=host, success=False, status_code=None) # Didn't get a response because of raise, so we dont have an status code
            
        match response.status_code:
            case 200:
                return ApplyResult(host=host, success=True, status_code=200)
            case 404:
                return ApplyResult(host=host, success=False, status_code=404)
            case _:
                return ApplyResult(host=host, success=False, status_code=response.status_code)
    
    async def create(self, host: str, group_id) -> ApplyResult:
        url = f"{host}/v1/group/"
        payload = {
                   "groupId": group_id
                  }
        
        try:
            response = await self._request(url=url, method=HttpMethods.POST, json=payload)
        except Exception as e:
            logger.warning("create_failed", host=host, error=str(e))
            return ApplyResult(host=host, success=False, status_code=None) # Didn't get a response because of raise, so we dont have an status code
            
        match response.status_code:
            case 201:
                return ApplyResult(host=host, success=True, status_code=201)
            case 400:
                state = await self.get_state(host, group_id=group_id)
                if state == NodeState.EXISTS:
                    return ApplyResult(host=host, success=True, status_code=400, msg="400 - Bad request. Perhaps the object exists.")
                return ApplyResult(host=host, success=False, status_code=400, msg="400 - Bad request. Perhaps the object exists.")
            case _:
                return ApplyResult(host=host, success=False, status_code=response.status_code)

