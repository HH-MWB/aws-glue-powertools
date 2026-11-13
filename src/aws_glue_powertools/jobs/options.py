"""AWS Glue CLI option filtering and argument resolution."""

from __future__ import annotations

from awsglue.utils import getResolvedOptions

__all__ = ["resolve_arguments"]

# =============================================================================
# AWS Glue CLI Constants
# =============================================================================

_SKIPPED_CLI_OPTIONS: frozenset[str] = frozenset(
    {
        # Identification & Metadata
        "JOB_ID",
        "JOB_RUN_ID",
        "SECURITY_CONFIGURATION",
        # Bookmarks & Continuation
        "job-bookmark-option",
        "continuation-option",
        "job-bookmark-from",
        "job-bookmark-to",
        # Security & Governance
        "encryption-type",
        "enable-data-lineage",
    },
)

_GLUE_PLATFORM_KEYS: frozenset[str] = frozenset(
    {
        # Identification & Metadata (owned by ctx.job)
        "JOB_NAME",
        "JOB_RUN_ID",
        "JOB_ID",
        "SECURITY_CONFIGURATION",
        # Bookmarks & Continuation (owned by ctx.job or internal)
        "job_bookmark_option",
        "continuation_option",
        "job_bookmark_from",
        "job_bookmark_to",
        # Security & Governance
        "encryption_type",
        "enable_data_lineage",
        # Staging & Storage (owned by ctx.job)
        "TempDir",
        "RedshiftTempDir",
        "spark_event_logs_path",
        # Engine & Table Formats (owned by ctx.job)
        "enable_auto_scaling",
        "datalake_formats",
        "conf",
        # Monitoring & Observability
        "enable_metrics",
        "enable_continuous_cloudwatch_log",
        "enable_continuous_log_filter",
        "enable_spark_ui",
        # Dependencies & Classpath
        "extra_py_files",
        "extra_jars",
        "extra_files",
        "user_jars_first",
        # Shuffle & Optimization
        "write_shuffle_files_to_s3",
        "write_shuffle_spills_to_s3",
    },
)


# =============================================================================
# Argument Resolution
# =============================================================================


def resolve_arguments(
    argv: list[str],
) -> tuple[dict[str, str], dict[str, str]]:
    """Resolve options into business payload and Glue system arguments.

    Args:
        argv: Command-line argument vector to resolve.

    Returns:
        A tuple of (business_args, glue_args).
    """
    options = [
        opt
        for arg in argv[1::2]
        if (opt := arg.removeprefix("--")) not in _SKIPPED_CLI_OPTIONS
    ]
    resolved = getResolvedOptions(argv, options)
    return (
        {k: v for k, v in resolved.items() if k not in _GLUE_PLATFORM_KEYS},
        {k: v for k, v in resolved.items() if k in _GLUE_PLATFORM_KEYS},
    )
