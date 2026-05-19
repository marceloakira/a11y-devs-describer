import httpx
import asyncio
import json

async def check():
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get("http://127.0.0.1:4096/doc")
        doc = r.json()
        
        paths = doc.get("paths", {})
        schemas = doc.get("components", {}).get("schemas", {})
        
        # 1. All paths with "message" or "session"
        msg_sess_paths = {}
        for path, methods in paths.items():
            if "message" in path.lower() or "session" in path.lower():
                msg_sess_paths[path] = methods
        
        # 2. All model-related endpoints
        model_paths = {}
        for path, methods in paths.items():
            path_lower = path.lower()
            methods_str = json.dumps(methods).lower()
            if "model" in path_lower or "model" in methods_str:
                # Check if it's actually about model info (not just model switch events)
                model_paths[path] = methods
        
        # 3. Schema summary
        schema_summary = {}
        for name, schema in schemas.items():
            props = schema.get("properties", {})
            fields = list(props.keys())
            schema_type = schema.get("type", "object")
            schema_summary[name] = {"type": schema_type, "fields": fields}
        
        result = {
            "message_session_paths": msg_sess_paths,
            "model_endpoints": model_paths,
            "schema_summary": schema_summary
        }
        
        with open(r"C:\Users\JHONATA\AppData\Local\Temp\opencode\full_api_extract.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        # Print summary
        print(f"Message/Session paths: {len(msg_sess_paths)}")
        for p in sorted(msg_sess_paths.keys()):
            methods = list(msg_sess_paths[p].keys())
            print(f"  {p} [{', '.join(methods)}]")
        
        print(f"\nModel endpoints: {len(model_paths)}")
        for p in sorted(model_paths.keys()):
            methods = list(model_paths[p].keys())
            print(f"  {p} [{', '.join(methods)}]")
        
        print(f"\nTotal schemas: {len(schema_summary)}")
        for name in sorted(schema_summary.keys()):
            info = schema_summary[name]
            fields_str = ', '.join(info['fields'][:15])
            dots = '...' if len(info['fields']) > 15 else ''
            print(f"  {name} ({info['type']}): {fields_str}{dots}")

asyncio.run(check())
