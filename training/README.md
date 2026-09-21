# Llama-3.2-3B 파인튜닝

AI 면접 도우미의 면접 질문 생성 / 답변 피드백을 위한 Llama-3.2-3B-Instruct QLoRA 파인튜닝 코드입니다.

## 왜 8B에서 3B로 바꿨나요

`Llama-3.2-8B`로 파인튜닝 시 CUDA `out of memory` 오류가 발생했다면, 대부분 GPU VRAM 부족이 원인입니다.
8B 모델은 4bit 양자화를 적용해도 학습 시 옵티마이저 상태, 그래디언트, 활성화 값까지 더해져 최소 10GB 이상의 VRAM이 필요한 경우가 많습니다.

> 참고: Meta가 공식 배포한 Llama 3.2 텍스트 모델은 **1B / 3B**만 존재합니다 (8B는 Llama 3.1, 11B/90B는 3.2의 비전(멀티모달) 모델입니다).
> 혹시 `meta-llama/Llama-3.2-8B` 같은 이름으로 받으셨다면 실제로는 다른 리포지토리를 받으셨을 가능성이 있으니 모델 ID를 다시 확인해보세요.

이 스크립트는 **3B 모델 + 4bit QLoRA + gradient checkpointing** 조합으로, 일반적인 8GB급 GPU(RTX 3070/4060 등)에서도 학습이 가능하도록 구성했습니다.

## 설치

```bash
# (선택) 가상환경
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r training/requirements.txt
```

Llama 3.2는 HuggingFace에서 라이선스 동의가 필요한 게이트 모델입니다.

1. https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct 에서 라이선스 동의
2. 터미널에서 로그인
   ```bash
   huggingface-cli login
   ```

## 데이터 준비

`training/data/sample_dataset.jsonl` 형식(JSONL, 줄마다 하나의 대화)을 참고해 자체 데이터를 준비하세요.

```json
{"messages": [
  {"role": "system", "content": "..."},
  {"role": "user", "content": "..."},
  {"role": "assistant", "content": "..."}
]}
```

질문 생성용 데이터와 답변 피드백용 데이터를 같은 파일에 섞어 두면 하나의 모델로 두 역할을 모두 처리하도록 학습됩니다(샘플 데이터셋 참고).

## 학습 실행

```bash
python training/finetune_llama.py \
  --data_path training/data/sample_dataset.jsonl \
  --output_dir training/output/llama-3.2-3b-interview
```

VRAM이 더 부족하면:

```bash
python training/finetune_llama.py \
  --per_device_train_batch_size 1 \
  --gradient_accumulation_steps 16 \
  --max_seq_length 512
```

VRAM이 24GB 이상으로 넉넉하다면 `--no_4bit`로 양자화 없이 학습할 수도 있습니다.

## 학습 결과 테스트

```bash
python training/inference.py \
  --adapter_dir training/output/llama-3.2-3b-interview \
  --prompt "자기소개서: ... 이 내용을 바탕으로 면접 질문 2개를 생성해주세요."
```

## 백엔드 연동

학습이 끝나면 `training/output/llama-3.2-3b-interview`에 LoRA 어댑터가 저장됩니다.
`backend/services/llm/kobert_service.py`처럼 `backend/services/llm/` 아래에 별도 서비스 모듈을 만들고,
`inference.py`의 모델 로딩 로직(`AutoModelForCausalLM` + `PeftModel.from_pretrained`)을 재사용해 FastAPI 라우터에 연결하면 됩니다.
