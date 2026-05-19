import httpx
import asyncio
import json

async def check():
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get("http://127.0.0.1:4096/doc")
        doc = r.json()
        
        paths = doc.get("paths", {})
        schemas = doc.get("components", {}).get("schemas", {})
        
        result = {}
        
        # 1. All paths with "message" or "session" in their name
        message_session_paths = {}
        for path, methods in paths.items():
            if "message" in path.lower() or "session" in path.lower():
                message_session_paths[path] = methods
        
        # 2. All component schema names with key fields
        schema_summary = {}
        for name, schema in schemas.items():
            props = schema.get("properties", {})
            key_fields = list(props.keys())[:20]  # top 20 fields
            schema_summary[name] = {
                "type": schema.get("type", "object"),
                "key_fields": key_fields
            }
        
        # 3. Any endpoint that returns model information
        model_endpoints = {}
        for path, methods in paths.items():
            path_str = json.dumps({path: methods})
            if "model" in path_str.lower():
                model_endpoints[path] = methods
        
        result["message_session_paths"] = message_session_paths
        result["schema_summary"] = schema_summary
        result["model_endpoints"] = model_endpoints
        
        with open(r"C:\Users\JHONATA\AppData\Local\Temp\opencode\api_analysis.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"Paths with message/session: {len(message_session_paths)}")
        for p in message_session_paths:
            print(f"  {p}")
        print(f"\nSchema count: {len(schema_summary)}")
        print(f"\nModel endpoints: {len(model_endpoints)}")
        for p in model_endpoints:
            print(f"  {p}")

asyncio.run(check())
