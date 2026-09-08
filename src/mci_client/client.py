import httpx
import asyncio

class Client:

    def __init__(self):
        self.client = httpx.