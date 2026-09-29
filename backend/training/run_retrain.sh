#!/bin/bash
# 선생님 데이터로 3B 점수 어댑터 재학습 → 평가. WSL 세션을 붙잡은 채 실행하고 완료·실패 시에만 출력한다.
#   bash run_retrain.sh train   : 분리 + 학습 (--resume 을 덧붙이면 마지막 체크포인트부터 이어서)
#   bash run_retrain.sh eval    : 새/기존 어댑터 평가 + 프로브 → eval_result.log
SRC=/mnt/c/Users/Owner/Desktop/Interview-Help-AI/backend/training
PY=~/venvs/llama-finetune/bin/python
NEW=output/llama-3.2-3b-score-teacher
OLD=output/llama-3.2-3b-score
cd ~/llama-train
cp $SRC/finetune_llama.py $SRC/split_teacher_dataset.py $SRC/eval_score_adapter.py $SRC/probe_score_range.py .

if [ "$1" = "train" ]; then
  $PY split_teacher_dataset.py data/score_teacher_qwen.jsonl 12 > retrain.log 2>&1
  $PY finetune_llama.py --data_path data/teacher_train.jsonl --output_dir $NEW \
    --num_train_epochs 3 --per_device_train_batch_size 2 --gradient_accumulation_steps 4 $2 >> retrain.log 2>&1
  code=$?
  if grep -q "저장 완료" retrain.log && [ $code -eq 0 ]; then
    echo "TRAIN_DONE: $(head -n 1 retrain.log) / $(tr '\r' '\n' < retrain.log | grep -o "'train_runtime': [0-9.]*")"
  else
    echo "TRAIN_FAILED (exit $code): $(tr '\r' '\n' < retrain.log | tail -c 400)"
  fi
elif [ "$1" = "eval" ]; then
  {
    echo "===== 새 어댑터 (선생님 데이터) — 평가셋"; $PY eval_score_adapter.py --adapter_dir $NEW --eval_path data/teacher_eval.jsonl
    echo "===== 기존 어댑터 (DB 데이터, 30/70) — 평가셋"; $PY eval_score_adapter.py --adapter_dir $OLD --eval_path data/teacher_eval.jsonl
    echo "===== 새 어댑터 — 프로브"; $PY probe_score_range.py --adapter_dir $NEW
    echo "===== 기존 어댑터 — 프로브"; $PY probe_score_range.py --adapter_dir $OLD
  } > eval_result.log 2>&1
  code=$?
  cp eval_result.log $SRC/eval_result.log
  grep -q "===== 기존 어댑터 — 프로브" eval_result.log && [ $code -eq 0 ] \
    && echo "EVAL_DONE" || echo "EVAL_FAILED (exit $code): $(tail -c 400 eval_result.log)"
fi
