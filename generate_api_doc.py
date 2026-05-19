"""Generate a comprehensive TXT documentation from the OpenCode OpenAPI spec."""
import json
from pathlib import Path

SPEC_PATH = Path("temp/opencode_api_full.json")
OUTPUT_PATH = Path("opencode_api_doc.txt")


def fmt_schema(schema, depth=0):
    """Format a JSON schema into readable text."""
    indent = "  " * depth
    if not isinstance(schema, dict):
        return str(schema)

    s_type = schema.get("type", "object")
    ref = schema.get("$ref", "")

    if ref:
        return ref.split("/")[-1]

    if s_type == "array":
        items = schema.get("items", {})
        item_desc = fmt_schema(items, depth)
        return f"Array<{item_desc}>"

    if s_type == "object":
        props = schema.get("properties", {})
        required = schema.get("required", [])
        if not props:
            any_of = schema.get("anyOf", [])
            one_of = schema.get("oneOf", [])
            if any_of or one_of:
                choices = any_of or one_of
                choice_strs = [fmt_schema(c, depth) for c in choices[:5]]
                result = f"Union({', '.join(choice_strs)})"
                if len(choices) > 5:
                    result += f" ...(+{len(choices) - 5} more)"
                return result
            return "Object{}"

        lines = ["Object {"]
        for name, prop in sorted(props.items()):
            req_mark = " *" if name in required else ""
            prop_desc = prop.get("description", "")
            prop_type = fmt_schema(prop, depth + 1)
            line = f"  {indent}{name}{req_mark}: {prop_type}"
            if prop_desc:
                line += f"  # {prop_desc}"
            lines.append(line)
        lines.append(f"{indent}}}")
        return "\n".join(lines)

    if s_type == "string":
        enum_vals = schema.get("enum", [])
        if enum_vals:
            return f"Enum[{', '.join(str(v) for v in enum_vals)}]"
        return "string"
    if s_type == "integer":
        return "integer"
    if s_type == "number":
        return "number"
    if s_type == "boolean":
        return "boolean"

    any_of = schema.get("anyOf", [])
    if any_of:
        choice_strs = [fmt_schema(c, depth) for c in any_of[:5]]
        result = f"Union({', '.join(choice_strs)})"
        if len(any_of) > 5:
            result += f" ...(+{len(any_of) - 5} more)"
        return result

    return s_type


def generate_doc():
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))

    lines = []
    sep = "=" * 80

    info = spec.get("info", {})
    lines.append(sep)
    lines.append("  OpenCode API Documentation")
    lines.append(f"  OpenAPI Version: {spec.get('openapi', 'N/A')}")
    lines.append(f"  API Title: {info.get('title', 'N/A')}")
    lines.append(f"  API Version: {info.get('version', 'N/A')}")
    desc = info.get("description", "")
    if desc:
        lines.append(f"  Description: {desc}")
    lines.append(sep)
    lines.append("")

    servers = spec.get("servers", [])
    if servers:
        lines.append("SERVERS")
        lines.append("-" * 40)
        for s in servers:
            lines.append(f"  {s.get('url', '')}  ({s.get('description', '')})")
        lines.append("")

    paths = spec.get("paths", {})
    lines.append("ENDPOINTS")
    lines.append(sep)

    for path, methods in sorted(paths.items()):
        lines.append("")
        lines.append(f"  {path}")
        lines.append(f"  {'~' * len(path)}")

        for method, details in methods.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue

            method_upper = method.upper()
            operation_id = details.get("operationId", "N/A")
            summary = details.get("summary", "")
            description = details.get("description", "")
            tags = details.get("tags", [])

            lines.append("")
            lines.append(f"    [{method_upper}] {operation_id}")
            if tags:
                lines.append(f"    Tags: {', '.join(tags)}")
            if summary:
                lines.append(f"    Summary: {summary}")
            if description:
                lines.append(f"    Description: {description}")

            params = details.get("parameters", [])
            if params:
                lines.append("    Parameters:")
                for p in params:
                    p_name = p.get("name", "")
                    p_in = p.get("in", "")
                    p_req = " (required)" if p.get("required") else ""
                    p_schema = p.get("schema", {})
                    p_type = p_schema.get("type", "any")
                    p_desc = p.get("description", "")
                    enum_vals = p_schema.get("enum", [])
                    enum_str = f" [{', '.join(enum_vals)}]" if enum_vals else ""
                    lines.append(f"      - {p_name} ({p_in}): {p_type}{p_req}{enum_str}")
                    if p_desc:
                        lines.append(f"        {p_desc}")

            body = details.get("requestBody", {})
            if body:
                content = body.get("content", {})
                json_content = content.get("application/json", {})
                body_schema = json_content.get("schema", {})
                lines.append("    Request Body:")
                lines.append(fmt_schema(body_schema, 3))

            responses = details.get("responses", {})
            if responses:
                lines.append("    Responses:")
                for code, resp in sorted(responses.items()):
                    resp_desc = resp.get("description", "")
                    resp_content = resp.get("content", {})
                    resp_schema = ""
                    if "application/json" in resp_content:
                        schema = resp_content["application/json"].get("schema", {})
                        resp_schema = fmt_schema(schema, 4)

                    lines.append(f"      {code}: {resp_desc}")
                    if resp_schema:
                        lines.append(resp_schema)

        lines.append("")
        lines.append("  " + "-" * 60)

    schemas = spec.get("components", {}).get("schemas", {})
    lines.append("")
    lines.append("")
    lines.append("SCHEMAS")
    lines.append(sep)

    for name in sorted(schemas.keys()):
        schema = schemas[name]
        desc = schema.get("description", "")
        lines.append("")
        lines.append(f"  {name}")
        lines.append(f"  {'~' * len(name)}")
        if desc:
            lines.append(f"    {desc}")
        lines.append(fmt_schema(schema, 2))
        lines.append("")

    lines.append(sep)
    lines.append(f"  Generated from OpenCode OpenAPI spec v{info.get('version', 'N/A')}")
    lines.append(sep)

    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Documentation written to: {OUTPUT_PATH}")
    print(f"Total lines: {len(lines)}")
    print(f"Total size: {OUTPUT_PATH.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    generate_doc()
