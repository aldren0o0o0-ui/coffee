class AppException(Exception):
    """Base application exception."""
    status_code = 500
    message = "An unexpected error occurred."

    def __init__(self, message=None, status_code=None, payload=None):
        if message is not None:
            self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload
        super().__init__(self.message)

    def __str__(self):
        return self.message

    def to_dict(self):
        rv = dict(self.payload or ())
        rv["status"] = "error"
        rv["message"] = self.message
        return rv


class ValidationError(AppException):
    status_code = 400
    message = "Validation failed for the submitted data."


class UnauthorizedError(AppException):
    status_code = 401
    message = "Authentication is required to perform this action."


class ForbiddenError(AppException):
    status_code = 403
    message = "You do not have permission to perform this action."


class NotFoundError(AppException):
    status_code = 404
    message = "Requested resource was not found."


class ConflictError(AppException):
    status_code = 409
    message = "A resource conflict occurred."


class InsufficientStockError(AppException):
    status_code = 400
    message = "Insufficient inventory stock to complete this transaction."


class ShiftClosedError(AppException):
    status_code = 400
    message = "POS register shift is closed. Open a shift first."
