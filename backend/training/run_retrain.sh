#!/bin/bash
# 선생님 데이터로 3B 점수 어댑터 재학습 → 평가. WSL 세션을 붙잡은 채 실행하고 완료·실패 시에만 출력한다.
#   bash run_retrain.sh train   : 분리 + 학습 (--resume 을 덧붙이면 마지막 체크포인트부터 이어서)
#   bash run_retrain.sh eval    : 새/기존(v1) 어댑터를 같은 평가셋으로 평가 + 프로브 → eval_result_$VER.log
#   VER=v21 bash run_retrain.sh train|eval   : v2.1 데이터(체크리스트 재채점)로 (기본 VER=v2)
SRC=/mnt/c/Users/Owner/Desktop/Interview-Help-AI/backend/training
PY=~/venvs/llama-finetune/bin/python
VER=${VER:-v2}
DATA=data/score_teacher_qwen_$VER.jsonl
NEW=output/llama-3.2-3b-score-$VER
OLD=output/llama-3.2-3b-score-teacher
TLOG=retrain_$VER.log
ELOG=eval_result_$VER.log
cd ~/llama-train
cp $SRC/finetune_llama.py $SRC/split_teacher_dataset.py $SRC/eval_score_adapter.py $SRC/probe_score_range.py .

if [ "$1" = "train" ]; then
  $PY split_teacher_dataset.py $DATA 24 > $TLOG 2>&1
  $PY finetune_llama.py --data_path data/teacher_train.jsonl --output_dir $NEW \
    --num_train_epochs 3 --per_device_train_batch_size 2 --gradient_accumulation_steps 4 $2 >> $TLOG 2>&1
  code=$?
  if grep -q "저장 완료" $TLOG && [ $code -eq 0 ]; then
    echo "TRAIN_DONE: $(head -n 1 $TLOG) / $(tr '\r' '\n' < $TLOG | grep -o "'train_runtime': [0-9.]*")"
  else
    echo "TRAIN_FAILED (exit $code): $(tr '\r' '\n' < $TLOG | tail -c 400)"
  fi
elif [ "$1" = "eval" ]; then
  {
    echo "===== $VER 어댑터 — $VER 평가셋"; $PY eval_score_adapter.py --adapter_dir $NEW --eval_path data/teacher_eval.jsonl
    echo "===== v1 어댑터 — $VER 평가셋"; $PY eval_score_adapter.py --adapter_dir $OLD --eval_path data/teacher_eval.jsonl
    echo "===== $VER 어댑터 — 프로브"; $PY probe_score_range.py --adapter_dir $NEW
    echo "===== v1 어댑터 — 프로브"; $PY probe_score_range.py --adapter_dir $OLD
  } > $ELOG 2>&1
  code=$?
  cp $ELOG $SRC/$ELOG
  grep -q "===== v1 어댑터 — 프로브" $ELOG && [ $code -eq 0 ] \
    && echo "EVAL_DONE" || echo "EVAL_FAILED (exit $code): $(tail -c 400 $ELOG)"
fi
