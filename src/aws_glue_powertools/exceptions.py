# pyright: reportImplicitStringConcatenation=false
"""Exceptions raised by AWS Glue Powertools."""

from __future__ import annotations

__all__ = [
    "GlueConnectionError",
    "GluePermissionError",
    "GluePowertoolsError",
]


class GluePowertoolsError(Exception):
    """Base exception for all AWS Glue Powertools errors."""


class GluePermissionError(PermissionError, GluePowertoolsError):
    """Raised when AWS Glue API operations lack required IAM permissions.

    Attributes:
        job_name: Name of the Glue job that encountered the error.
        action: AWS IAM action that lacked permissions.
    """

    def __init__(self, job_name: str, action: str) -> None:
        """Initialize GluePermissionError.

        Args:
            job_name: Name of the Glue job.
            action: Required AWS IAM action.
        """
        self.job_name = job_name
        self.action = action
        super().__init__(
            f"Failed to fetch telemetry for Glue job '{job_name}'. "
            f"Ensure the execution role has '{action}' permissions.",
        )


class GlueConnectionError(ConnectionError, GluePowertoolsError):
    """Raised when connection to the AWS Glue service endpoint fails.

    Attributes:
        job_name: Name of the Glue job that encountered the error.
    """

    def __init__(self, job_name: str) -> None:
        """Initialize GlueConnectionError.

        Args:
            job_name: Name of the Glue job.
        """
        self.job_name = job_name
        super().__init__(
            "Failed to connect to AWS Glue service endpoint for "
            f"job '{job_name}'. Ensure the VPC subnet has a route "
            "to a Glue VPC Endpoint or NAT Gateway.",
        )
