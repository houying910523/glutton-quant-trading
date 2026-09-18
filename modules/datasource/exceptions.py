class ConfigurationError(ValueError):
    """Raised when the sync request or runtime is misconfigured."""


class PipelineExecutionError(RuntimeError):
    """Raised when a pipeline cannot finish successfully."""
