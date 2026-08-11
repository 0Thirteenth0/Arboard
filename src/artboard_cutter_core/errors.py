class ExportError(RuntimeError):
    """Base exception for a failed export job."""


class ExportCancelled(ExportError):
    """Raised when the user requests cooperative export cancellation."""

