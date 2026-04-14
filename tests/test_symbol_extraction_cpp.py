from app.analyzers.symbols import extract_symbols
from app.parsers.tree_sitter import parse_source_code
from app.schemas.symbols import SymbolKind


def test_cpp_symbol_extraction() -> None:
    parsed = parse_source_code(
        """
namespace demo {
template <typename T>
struct Box {
public:
    T value;

    T get() {
        T copy = value;
        return copy;
    }
};

enum class Color : int {
    Red = 1,
    Blue = 2
};

union Value {
    int number;
    float ratio;
};

int helper(int input) {
    int local = input + 1;
    return local;
}
}
""".strip(),
        "cpp",
        path="sample.cpp",
    )

    result = extract_symbols(parsed)
    symbols = {(symbol.kind, symbol.qualified_name): symbol for symbol in result.symbols}

    assert (SymbolKind.FILE, "sample.cpp") in symbols
    assert (SymbolKind.NAMESPACE, "demo") in symbols
    assert (SymbolKind.STRUCT, "demo.Box") in symbols
    assert (SymbolKind.VARIABLE, "demo.Box.value") in symbols
    assert (SymbolKind.METHOD, "demo.Box.get") in symbols
    assert (SymbolKind.VARIABLE, "demo.Box.get.copy") in symbols
    assert (SymbolKind.ENUM, "demo.Color") in symbols
    assert (SymbolKind.ENUM_MEMBER, "demo.Color.Red") in symbols
    assert (SymbolKind.UNION, "demo.Value") in symbols
    assert (SymbolKind.VARIABLE, "demo.Value.number") in symbols
    assert (SymbolKind.FUNCTION, "demo.helper") in symbols
    assert (SymbolKind.VARIABLE, "demo.helper.local") in symbols
