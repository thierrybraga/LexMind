import asyncio
import sys
import os

# Adicionar o diretório backend ao path para garantir que 'app' seja encontrado
# Dentro do container, o backend está em /app/backend
sys.path.append("/app/backend")
# Também mantém compatibilidade local (adiciona backend ao path)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_path = os.path.join(project_root, 'backend')
sys.path.append(backend_path)

from app.core.config import settings
from openai import AsyncOpenAI

async def test_openai():
    print("Testing OpenAI connection...")
    print(f"Model: {settings.OPENAI_MODEL}")

    # 1. Testar conectividade básica (list models)
    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        models = await client.models.list()
        model_ids = [m.id for m in models.data]
        print("✅ Connection successful!")
        print(f"Available models: {model_ids[:10]}")
        if settings.OPENAI_MODEL in model_ids:
            print(f"✅ Model '{settings.OPENAI_MODEL}' found.")
        else:
            print(f"❌ Model '{settings.OPENAI_MODEL}' NOT found.")
    except Exception as e:
        print(f"❌ Connection error: {e}")

    # 2. Testar geração (Chat)
    print("\nTesting Chat Generation...")
    try:
        from app.core.llm import LLMEngine
        engine = LLMEngine()
        
        prompt = "Qual a capital do Brasil? Responda em uma palavra."
        print(f"Prompt: {prompt}")
        
        response, _ = await engine._call_openai(prompt)
        print(f"✅ Response: {response}")
        
    except Exception as e:
        print(f"❌ Chat generation error: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_openai())
