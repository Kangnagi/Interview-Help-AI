import os, asyncio, sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv(override=True)

key = os.getenv('GEMINI_API_KEY')
print(f'KEY exists: {bool(key)}, length: {len(key) if key else 0}')
model = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
print(f'MODEL: {model}')

from google import genai
client = genai.Client(api_key=key)

# 모델 목록 확인
try:
    models = [m.name for m in client.models.list()]
    flash_models = [m for m in models if 'flash' in m.lower()]
    print(f'Flash models available: {flash_models[:5]}')
except Exception as e:
    print(f'Model list error: {e}')

async def test():
    for m in ['gemini-2.5-flash', 'gemini-2.0-flash-lite', 'gemini-2.0-flash']:
        try:
            resp = await client.aio.models.generate_content(
                model=m,
                contents='한국어로 "API 정상 동작"이라고만 답하세요.'
            )
            print(f'✅ [{m}] Response: {resp.text.strip()}')
            break
        except Exception as e:
            print(f'❌ [{m}] Error: {type(e).__name__}: {str(e)[:120]}')

asyncio.run(test())
