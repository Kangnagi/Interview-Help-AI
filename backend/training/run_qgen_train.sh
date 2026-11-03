#!/bin/bash
# 질문 전용 어댑터 학습 (WSL) — 완료 · 실패 시에만 한 줄 출력
#   bash run_qgen_train.sh check      : 답변 부분만 학습되는지(정답 범위 · 끝 토큰) 확인
#   bash run_qgen_train.sh train q1   : Bllossom-3B에서 새 LoRA로 학습 (data/qgen_train_msgs.jsonl, build_qgen_dataset.py로 생성)
# 결과: ~/llama-train/output/bllossom-qgen-<이름> → Windows backend/ai_models/ 로 복사
SRC=/mnt/c/Users/Owner/Desktop/Interview-Help-AI/backend/training
BLLOSSOM=~/models/llama-3.2-Korean-Bllossom-3B
PY=~/venvs/llama-finetune/bin/python
cd ~/llama-train
cp $SRC/finetune_llama.py .
cp $SRC/data/qgen_train_msgs.jsonl data/

if [ "$1" = "check" ]; then
  $PY - <<'EOF' 2>&1 | grep -v -i warn
import json, os
from transformers import AutoTokenizer
from trl import DataCollatorForCompletionOnlyLM
from finetune_llama import ASSISTANT_HEADER
tok = AutoTokenizer.from_pretrained(os.path.expanduser("~/models/llama-3.2-Korean-Bllossom-3B"))
tok.pad_token = "<|finetune_right_pad_id|>"
rows = [json.loads(l) for l in open("data/qgen_train_msgs.jsonl", encoding="utf-8")][:2] + \
       [json.loads(l) for l in open("data/qgen_train_msgs.jsonl", encoding="utf-8")][-1:]
col = DataCollatorForCompletionOnlyLM(tok(ASSISTANT_HEADER, add_special_tokens=False).input_ids, tokenizer=tok)
batch = col([tok(tok.apply_chat_template(r["messages"], tokenize=False)) for r in rows])
for i, r in enumerate(rows):
    lab = [t for t in batch["labels"][i].tolist() if t != -100]
    text = tok.decode(lab)
    ok = text.strip().endswith("<|eot_id|>") and r["messages"][-1]["content"][:20] in text
    print(f"CHECK {'OK' if ok else 'FAIL'}: 학습 토큰 {len(lab)}개 — {text[:60]!r} … {text[-20:]!r}")
EOF
elif [ "$1" = "train" ]; then
  NAME=$2; OUT=output/bllossom-qgen-$NAME; LOG=train_qgen_$NAME.log
  [ "$3" = "--resume" ] || rm -f $LOG
  $PY finetune_llama.py --data_path data/qgen_train_msgs.jsonl --output_dir $OUT --model_name $BLLOSSOM \
    --completion_only --num_train_epochs 3 --per_device_train_batch_size 2 --gradient_accumulation_steps 4 \
    --learning_rate 2e-4 --save_steps 100 $3 >> $LOG 2>&1
  code=$?
  if grep -q "저장 완료" $LOG && [ $code -eq 0 ]; then
    echo "TRAIN_DONE $NAME: $(tr '\r' '\n' < $LOG | grep -o "'train_runtime': [0-9.]*" | tail -n 1) $(tr '\r' '\n' < $LOG | grep -o "'train_loss': [0-9.]*" | tail -n 1)"
  else
    echo "TRAIN_FAILED $NAME (exit $code): $(tr '\r' '\n' < $LOG | tail -c 300)"
  fi
fi
