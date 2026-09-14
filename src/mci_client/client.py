from enum import Enum

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
)

from mci_client.models import ApplyResult, NodeState
from mci_client.schemas import GroupRequest

logger = structlog.get_logger(__name__)


class HttpMethods(str, Enum):
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"


class Client:

    def __init__(self,
                 timeout: float = 5,
                 attempts: int = 5,
                 max_retry_time: float = 60.0):
        self._client = httpx.AsyncClient(timeout=timeout)
        self._attempts = attempts
        self._max_retry_time = max_retry_time
        
        # the retry is a decorator method, but as i wanted to use it with the configured values that get initiated in my client,
        # I prefered to make it an inside method to run it by a call in our functions.  
        self._retry = retry(
            stop=stop_after_attempt(self._attempts) | stop_after_delay(self._max_retry_time),
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
        
        logger.debug("http_request", method=method.value, url=url)
        response = await self._retry(self._client.request)(method=method.value, url=url, json=json)
        logger.debug(
            "http_response",
            method=method.value,
            url=url,
            status=response.status_code,
        )
        return response
    
    async def get_state(self, host: str, group_id: str) -> NodeState:
        
        url = f"{host}/v1/group/{group_id}/"
        logger.info("get_state_started", host=host, group_id=group_id)
        
        try:
            response = await self._request(url=url, method=HttpMethods.GET)
        except Exception as e:  # noqa: BLE001
            logger.warning("get_state_failed", host=host, error=str(e))
            return NodeState.UNKNOWN
            
        match response.status_code:
            case 200:
                logger.info("get_state_ok", host=host, group_id=group_id, state="EXISTS")
                return NodeState.EXISTS
            case 404:
                logger.info("get_state_ok", host=host, group_id=group_id, state="ABSENT")
                return NodeState.ABSENT
            case _:
                logger.warning("get_state_unexpected_status", host=host, group_id=group_id, status=response.status_code)
                return NodeState.UNKNOWN

    async def delete(self, host: str, group_id) -> ApplyResult:
        
        url = f"{host}/v1/group/"
        payload = GroupRequest(groupId=group_id).model_dump(by_alias=True)
        
        logger.info("delete_started", host=host, group_id=group_id)

        try:
            response = await self._request(url=url, method=HttpMethods.DELETE, json=payload)
        except Exception as e: # noqa: BLE001
            logger.warning("delete_failed", host=host, error=str(e))
            return ApplyResult(host=host, success=False, status_code=None) # Didn't get a response because of raise, so we dont have an status code
            
        match response.status_code:
            case 200:
                logger.info("delete_ok", host=host, group_id=group_id, status=200)
                return ApplyResult(host=host, success=True, status_code=200)
            case 404:
                logger.info("delete_not_found", host=host, group_id=group_id, status=404)
                return ApplyResult(host=host, success=True, status_code=404)
            case _:
                logger.warning("delete_failed_unexpected_status", host=host, group_id=group_id, status=response.status_code)
                return ApplyResult(host=host, success=False, status_code=response.status_code)
    
    async def create(self, host: str, group_id) -> ApplyResult:
        
        url = f"{host}/v1/group/"
        payload = GroupRequest(groupId=group_id).model_dump(by_alias=True)
        
        logger.info("create_started", host=host, group_id=group_id)
        
        try:
            response = await self._request(url=url, method=HttpMethods.POST, json=payload)
        except Exception as e: # noqa: BLE001
            logger.warning("create_failed", host=host, error=str(e))
            return ApplyResult(host=host, success=False, status_code=None) # Didn't get a response because of raise, so we dont have an status code
            
        match response.status_code:
            case 201:
                logger.info("create_ok", host=host, group_id=group_id, status=201)
                return ApplyResult(host=host, success=True, status_code=201)
            
            case 400:
                logger.info("create_400_verifying", host=host, group_id=group_id, msg="400 received, checking if group already exists")
                state = await self.get_state(host, group_id=group_id)
                
                if state == NodeState.EXISTS:
                    logger.info( "create_ok_already_exists", host=host, group_id=group_id, status=400)
                    return ApplyResult(host=host, success=True, status_code=400, msg="400 - Bad request. Perhaps the object exists.")
                
                logger.warning( "create_failed_bad_request", host=host, group_id=group_id, status=400,)
                return ApplyResult(host=host, success=False, status_code=400, msg="400 - Bad request. Perhaps the object exists.")
            
            case _:
                logger.warning("create_failed_unexpected_status", host=host, group_id=group_id, status=response.status_code)
                return ApplyResult(host=host, success=False, status_code=response.status_code)

