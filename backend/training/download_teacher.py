"""선생님 모델(Qwen2.5-14B-Instruct, Apache 2.0) 다운로드 — 학습 데이터 생성에만 쓰고 서비스에는 들어가지 않는다."""
from huggingface_hub import snapshot_download

path = snapshot_download(
    "Qwen/Qwen2.5-14B-Instruct",
    allow_patterns=["*.json", "*.safetensors", "*.txt", "tokenizer*", "merges.txt", "vocab.json"],
)
print(f"DOWNLOAD_DONE {path}", flush=True)
