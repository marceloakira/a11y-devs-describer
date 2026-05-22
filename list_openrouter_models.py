import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

async def list_free_vision_models():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("OPENROUTER_API_KEY não encontrada.")
        return

    url = "https://openrouter.ai/api/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                print(f"Erro ao listar modelos: {response.status_code}")
                return

            models = response.json().get("data", [])
            print("--- Modelos Gratuitos (com :free) ---")
            found = False
            for m in models:
                mid = m.get("id", "")
                if ":free" in mid:
                    # Verifica se o modelo suporta imagem (geralmente tem 'vision' ou 'vl' no nome)
                    # ou se é um modelo conhecido de visão
                    is_vision = any(x in mid.lower() for x in ["vision", "vl", "gemini", "llama-3.2-11b", "pixtral"])
                    vision_tag = "[VISION?]" if is_vision else ""
                    print(f"- {mid} {vision_tag}")
                    found = True
            
            if not found:
                print("Nenhum modelo gratuito encontrado.")

    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    asyncio.run(list_free_vision_models())
