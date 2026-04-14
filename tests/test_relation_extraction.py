from app.analyzers.relations import extract_relations
from app.parsers.tree_sitter import parse_source_code
from app.schemas.relations import RelationKind


def test_python_contains_relations_are_extracted() -> None:
    parsed = parse_source_code(
        """
class Greeter:
    prefix = "hi"

    def greet(self, name):
        message = f"{self.prefix} {name}"
        return message
""".strip(),
        "python",
        path="sample.py",
    )

    result = extract_relations(parsed)
    relations = {(relation.kind, relation.source, relation.destination): relation for relation in result.relations}

    assert (RelationKind.CONTAINS, "sample.py", "Greeter") in relations
    assert (RelationKind.CONTAINS, "Greeter", "Greeter.prefix") in relations
    assert (RelationKind.CONTAINS, "Greeter", "Greeter.greet") in relations
    assert (RelationKind.CONTAINS, "Greeter.greet", "Greeter.greet.message") in relations


def test_python_calls_relations_are_extracted() -> None:
    parsed = parse_source_code(
        """
class Greeter:
    def greet(self, name):
        helper(name)
        self.render(name)
""".strip(),
        "python",
        path="sample.py",
    )

    result = extract_relations(parsed)
    relations = {(relation.kind, relation.source, relation.destination): relation for relation in result.relations}

    assert (RelationKind.CALLS, "Greeter.greet", "helper") in relations
    assert (RelationKind.CALLS, "Greeter.greet", "self.render") in relations


def test_java_contains_and_imports_relations_are_extracted() -> None:
    parsed = parse_source_code(
        """
package demo.core;
import static demo.util.Names.DEFAULT_NAME;
import demo.shared.BaseService;

class Service extends BaseService {
    class Formatter {}

    String greet(String name) {
        String message = name;
        return message;
    }
}
""".strip(),
        "java",
        path="Service.java",
    )

    result = extract_relations(parsed)
    relations = {(relation.kind, relation.source, relation.destination): relation for relation in result.relations}

    assert (RelationKind.CONTAINS, "Service.java", "demo.shared.BaseService") in relations
    assert (RelationKind.CONTAINS, "Service.java", "static:demo.util.Names.DEFAULT_NAME") in relations
    assert (RelationKind.CONTAINS, "Service.java", "demo.core.Service") in relations
    assert (RelationKind.CONTAINS, "demo.core.Service", "demo.core.Service.Formatter") in relations
    assert (RelationKind.CONTAINS, "demo.core.Service", "demo.core.Service.greet") in relations
    assert (RelationKind.IMPORTS, "Service.java", "demo.shared.BaseService") in relations
    assert (RelationKind.IMPORTS, "Service.java", "demo.util.Names.DEFAULT_NAME") in relations
    assert relations[(RelationKind.IMPORTS, "Service.java", "demo.util.Names.DEFAULT_NAME")].metadata == {"is_static": True}


def test_java_calls_relations_are_extracted() -> None:
    parsed = parse_source_code(
        """
class Service {
    String greet(String name) {
        helper(name);
        this.render(name);
        return name;
    }
}
""".strip(),
        "java",
        path="Service.java",
    )

    result = extract_relations(parsed)
    relations = {(relation.kind, relation.source, relation.destination): relation for relation in result.relations}

    assert (RelationKind.CALLS, "Service.greet", "helper") in relations
    assert (RelationKind.CALLS, "Service.greet", "this.render") in relations


def test_cpp_contains_and_imports_relations_are_extracted() -> None:
    parsed = parse_source_code(
        """
namespace demo {
using size_type = long;
using std::string;

struct Box {
    struct Inner {
        int id;
    };
};
}
""".strip(),
        "cpp",
        path="sample.cpp",
    )

    result = extract_relations(parsed)
    relations = {(relation.kind, relation.source, relation.destination): relation for relation in result.relations}

    assert (RelationKind.CONTAINS, "sample.cpp", "demo") in relations
    assert (RelationKind.CONTAINS, "demo", "demo.size_type") in relations
    assert (RelationKind.CONTAINS, "demo", "std::string") in relations
    assert (RelationKind.CONTAINS, "demo", "demo.Box") in relations
    assert (RelationKind.CONTAINS, "demo.Box", "demo.Box.Inner") in relations
    assert (RelationKind.CONTAINS, "demo.Box.Inner", "demo.Box.Inner.id") in relations
    assert (RelationKind.IMPORTS, "sample.cpp", "std::string") in relations
    assert relations[(RelationKind.IMPORTS, "sample.cpp", "std::string")].metadata == {"is_static": False}


def test_c_and_cpp_calls_relations_are_extracted() -> None:
    c_parsed = parse_source_code(
        "int add(int a) { log(a); return helper(a); }",
        "c",
        path="sample.c",
    )
    cpp_parsed = parse_source_code(
        """
struct Box {
    int run(int value) {
        log(value);
        return helper(value);
    }
};
""".strip(),
        "cpp",
        path="sample.cpp",
    )

    c_result = extract_relations(c_parsed)
    cpp_result = extract_relations(cpp_parsed)
    c_relations = {(relation.kind, relation.source, relation.destination): relation for relation in c_result.relations}
    cpp_relations = {(relation.kind, relation.source, relation.destination): relation for relation in cpp_result.relations}

    assert (RelationKind.CALLS, "add", "log") in c_relations
    assert (RelationKind.CALLS, "add", "helper") in c_relations
    assert (RelationKind.CALLS, "Box.run", "log") in cpp_relations
    assert (RelationKind.CALLS, "Box.run", "helper") in cpp_relations
