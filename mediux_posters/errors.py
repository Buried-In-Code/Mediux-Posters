__all__ = ["AuthenticationError", "ServiceError"]


class ServiceError(Exception): ...


class AuthenticationError(ServiceError): ...
