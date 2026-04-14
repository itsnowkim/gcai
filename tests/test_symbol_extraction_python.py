from app.analyzers.symbols import extract_symbols
from app.parsers.tree_sitter import parse_source_code
from app.schemas.symbols import SymbolKind


def test_python_symbol_extraction() -> None:
    parsed = parse_source_code(
        """
@decorator
class Greeter:
    prefix = "hi"

    def greet(self, name):
        message = f"{self.prefix} {name}"
        return message

@classmethod
async def helper(value):
    total = value + 1
    return total
""".strip(),
        "python",
        path="sample.py",
    )

    result = extract_symbols(parsed)
    symbols = {(symbol.kind, symbol.qualified_name): symbol for symbol in result.symbols}

    assert (SymbolKind.FILE, "sample.py") in symbols
    assert (SymbolKind.CLASS, "Greeter") in symbols
    assert (SymbolKind.METHOD, "Greeter.greet") in symbols
    assert (SymbolKind.VARIABLE, "Greeter.prefix") in symbols
    assert (SymbolKind.VARIABLE, "Greeter.greet.message") in symbols
    assert (SymbolKind.FUNCTION, "helper") in symbols
    assert (SymbolKind.VARIABLE, "helper.total") in symbols
    assert symbols[(SymbolKind.METHOD, "Greeter.greet")].body is not None
