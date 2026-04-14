from app.analyzers.symbols import extract_symbols
from app.parsers.tree_sitter import parse_source_code
from app.schemas.symbols import SymbolKind


def test_c_symbol_extraction() -> None:
    parsed = parse_source_code(
        """
typedef unsigned long size_t;

typedef struct Point {
    int x;
    int y;
} Point;

enum Color {
    RED = 1,
    BLUE
};

union Value {
    int number;
    float ratio;
};

int counter = 0;

static int add(int a, int b) {
    int total = a + b;
    return total;
}
""".strip(),
        "c",
        path="sample.c",
    )

    result = extract_symbols(parsed)
    symbols = {(symbol.kind, symbol.qualified_name): symbol for symbol in result.symbols}

    assert (SymbolKind.FILE, "sample.c") in symbols
    assert (SymbolKind.TYPE_ALIAS, "size_t") in symbols
    assert symbols[(SymbolKind.TYPE_ALIAS, "size_t")].aliased_type == "unsigned long"
    assert (SymbolKind.STRUCT, "Point") in symbols
    assert (SymbolKind.TYPE_ALIAS, "Point") in symbols
    assert symbols[(SymbolKind.TYPE_ALIAS, "Point")].aliased_type.startswith("struct Point")
    assert (SymbolKind.VARIABLE, "Point.x") in symbols
    assert (SymbolKind.ENUM, "Color") in symbols
    assert (SymbolKind.ENUM_MEMBER, "Color.RED") in symbols
    assert (SymbolKind.UNION, "Value") in symbols
    assert (SymbolKind.VARIABLE, "Value.number") in symbols
    assert (SymbolKind.VARIABLE, "counter") in symbols
    assert (SymbolKind.FUNCTION, "add") in symbols
    assert symbols[(SymbolKind.FUNCTION, "add")].parameters == ["int a", "int b"]
    assert (SymbolKind.VARIABLE, "add.total") in symbols
    assert "static int add(int a, int b)" in symbols[(SymbolKind.FUNCTION, "add")].signature
