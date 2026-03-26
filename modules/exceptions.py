"""Custom exception hierarchy for the Attendance System."""


class AttendanceAppError(Exception):
    """Base exception for the attendance system."""


class DataFormatError(AttendanceAppError):
    """Raised when input data has unexpected structure or missing columns."""


class ParsingError(AttendanceAppError):
    """Raised when data parsing fails due to malformed cell values."""
