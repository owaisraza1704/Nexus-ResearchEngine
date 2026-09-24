from uuid import UUID


class NexusError(Exception):
    """A safe application error returned by the API and recorded on a query."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 422,
        *,
        retryable: bool = False,
        query_id: UUID | None = None,
        run_id: UUID | None = None,
        job_id: UUID | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.retryable = retryable
        self.query_id = query_id
        self.run_id = run_id
        self.job_id = job_id
