import httpx
import structlog
from enum import Enum
from tenacity import (retry,
                      retry_if_exception_type,
                      stop_after_attempt,
                      stop_after_delay,
                      wait_exponential)


logger = structlog.get_logger(__name__)


class HttpMethods(str, Enum):
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"


class Client:

    def __init__(self, timeout: int | float = 5, attempts:int = 5):
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
    
    async def _close(self):
        await self._client.aclose()
        logger.info("Client Closed")
        
    
    async def _request(self, url: str, method:HttpMethods, json: dict) -> httpx.Response:
        return await self._retry(self._client.request)(method=method.value, url=url, json=json)
        