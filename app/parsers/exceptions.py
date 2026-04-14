from app.core.exceptions import GCAIError


class ParserConfigurationError(GCAIError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, error_code="parser_configuration_error", status_code=500)


class UnsupportedLanguageError(GCAIError):
    def __init__(self, path: str) -> None:
        super().__init__(
            message=f"Unsupported source file extension for parsing: {path}",
            error_code="unsupported_language",
            status_code=400,
        )


class SourceFileReadError(GCAIError):
    def __init__(self, path: str) -> None:
        super().__init__(
            message=f"Unable to read source file: {path}",
            error_code="source_file_read_error",
            status_code=400,
        )


class SourceParseError(GCAIError):
    def __init__(self, detail: str) -> None:
        super().__init__(message=detail, error_code="source_parse_error", status_code=400)
