from app.analyzers.symbols import extract_symbols
from app.parsers.tree_sitter import parse_source_code
from app.schemas.symbols import SymbolKind


def test_java_symbol_extraction() -> None:
    parsed = parse_source_code(
        """
package demo.core;
import static demo.util.Names.DEFAULT_NAME;
import demo.shared.BaseService;
import demo.shared.Greeter;

interface Greeter {
    String greet(String name);
}

enum Color {
    RED,
    BLUE;

    private int code = 1;

    Color() {}
}

record User(String name, int age) {}

@interface Marker {}

class Service extends BaseService implements Greeter {
    private String prefix = "hi";

    class Formatter {
        String decorate(String value) {
            return value;
        }
    }

    Service() {}

    String greet(String name) {
        String message = prefix + name;
        return message;
    }
}
""".strip(),
        "java",
        path="Greeter.java",
    )

    result = extract_symbols(parsed)
    symbols = {(symbol.kind, symbol.qualified_name): symbol for symbol in result.symbols}

    assert (SymbolKind.FILE, "Greeter.java") in symbols
    assert (SymbolKind.IMPORT, "static:demo.util.Names.DEFAULT_NAME") in symbols
    assert symbols[(SymbolKind.IMPORT, "static:demo.util.Names.DEFAULT_NAME")].is_static is True
    assert (SymbolKind.IMPORT, "demo.shared.BaseService") in symbols
    assert (SymbolKind.INTERFACE, "demo.core.Greeter") in symbols
    assert (SymbolKind.ENUM, "demo.core.Color") in symbols
    assert (SymbolKind.ENUM_MEMBER, "demo.core.Color.RED") in symbols
    assert (SymbolKind.RECORD, "demo.core.User") in symbols
    assert (SymbolKind.ANNOTATION, "demo.core.Marker") in symbols
    assert (SymbolKind.CLASS, "demo.core.Service") in symbols
    assert symbols[(SymbolKind.CLASS, "demo.core.Service")].super_types == ["BaseService", "Greeter"]
    assert (SymbolKind.CLASS, "demo.core.Service.Formatter") in symbols
    assert (SymbolKind.CONSTRUCTOR, "demo.core.Service.Service") in symbols
    assert (SymbolKind.METHOD, "demo.core.Service.greet") in symbols
    assert symbols[(SymbolKind.METHOD, "demo.core.Service.greet")].parameters == ["String name"]
    assert (SymbolKind.METHOD, "demo.core.Service.Formatter.decorate") in symbols
    assert (SymbolKind.VARIABLE, "demo.core.Service.prefix") in symbols
    assert (SymbolKind.VARIABLE, "demo.core.Service.greet.message") in symbols
    assert "String greet(String name)" in symbols[(SymbolKind.METHOD, "demo.core.Service.greet")].signature
