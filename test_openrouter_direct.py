import asyncio
import base64
import httpx
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega as configurações do .env
load_dotenv()

async def test_openrouter_vision():
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.2-11b-vision-instruct:free")
    
    if not api_key or api_key == "sua_chave_aqui":
        print("ERRO: OPENROUTER_API_KEY não configurada no .env")
        return

    print(f"--- Iniciando Teste OpenRouter ---")
    print(f"Modelo: {model}")
    print(f"Chave: {api_key[:10]}...{api_key[-5:]}")

    # Cria uma imagem preta simples (1x1 pixel) em base64 para o teste
    # Isso evita depender de um arquivo externo para o teste básico de conexão
    pixel_data = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
    b64_image = base64.b64encode(pixel_data).decode("utf-8")

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "O que você vê nesta imagem? Responda apenas 'OK' se conseguir ver."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/gif;base64,{b64_image}"
                        }
                    }
                ]
            }
        ]
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/bot-acess",
        "X-Title": "Bot Acess Test Script",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            print("Enviando requisição...")
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers=headers
            )
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code != 200:
                print(f"ERRO DA API: {response.text}")
                return

            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                result = data["choices"][0]["message"]["content"]
                print(f"RESPOSTA DA IA: {result}")
                print("\n✅ TESTE CONCLUÍDO COM SUCESSO!")
            else:
                print(f"RESPOSTA INESPERADA: {data}")

    except Exception as e:
        print(f"ERRO AO EXECUTAR TESTE: {e}")

if __name__ == "__main__":
    asyncio.run(test_openrouter_vision())
