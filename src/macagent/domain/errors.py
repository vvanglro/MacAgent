class MacAgentError(Exception):
    """Base exception for all MacAgent failures."""


class ParseError(MacAgentError):
    """Raised when natural language cannot be parsed into a known action."""


class GuardrailError(MacAgentError):
    """Raised when a parsed action fails safety policy validation."""


class ExecutionError(MacAgentError):
    """Raised when tool execution fails."""
