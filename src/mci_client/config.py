from typing import Annotated
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode


class ClusterConfig(BaseSettings):

    model_config = {"env_prefix": "MCI_"}

    hosts: Annotated[list[str], NoDecode] = Field(
        ...,
        description="Hostname Importation is required.",
        examples=[
            'http://node1.example.com',
            'http://node2.example.com',
            'http://node3.example.com',
        ],
    )
    rounds: int =5
    timeout: float = Field(5.0, ge=1.0, le=60.0)
    delay: float = Field(0.5, ge=0.0, le=10.0)
    attempts: int = Field(5, ge=1, le=10)
    max_retry_time: float = Field(15.0, ge=1.0, le=120.0)
    log_level: str = "INFO"
    
    @field_validator("hosts", mode="before")
    @classmethod
    def parse_hosts(cls, v):
        
        if isinstance(v, str):
            if not v.strip():
                raise ValueError('Hosts list can not be empty!')
            return [host.strip() for host in v.split(",") if host.strip()]
        return v

    @field_validator('hosts')
    @classmethod
    def validate_hosts(cls,v):
        for host in v:
            prased_url = urlparse(host)
            if not prased_url.scheme or not prased_url.netloc:
                raise ValueError(f"Invalid host URL: {host}")
        return v
