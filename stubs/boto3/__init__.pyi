from datetime import datetime
from typing import NotRequired, Protocol, TypedDict

class JobRunTypeDef(TypedDict):
    Attempt: int
    StartedOn: datetime
    Timeout: int
    WorkerType: str
    NumberOfWorkers: int
    GlueVersion: str
    ExecutionClass: NotRequired[str]

class GetJobRunResponse(TypedDict):
    JobRun: JobRunTypeDef

class GlueClient(Protocol):
    def get_job_run(
        self,
        *,
        JobName: str,
        RunId: str,
    ) -> GetJobRunResponse: ...

def client(service_name: str) -> GlueClient: ...
