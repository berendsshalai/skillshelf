class OperationalRuntimeError(RuntimeError):
    """Base error for failures that must be persisted in the run ledger."""


class DelegationDepthExceeded(OperationalRuntimeError):
    pass
