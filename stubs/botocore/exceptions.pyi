class BotoCoreError(Exception): ...

class ClientError(BotoCoreError):
    response: dict[str, dict[str, str]]
    operation_name: str
    def __init__(
        self,
        error_response: dict[str, dict[str, str]],
        operation_name: str,
    ) -> None: ...

class EndpointConnectionError(BotoCoreError):
    endpoint_url: str
    def __init__(self, *, endpoint_url: str) -> None: ...

class ConnectTimeoutError(BotoCoreError):
    endpoint_url: str
    def __init__(self, *, endpoint_url: str) -> None: ...
