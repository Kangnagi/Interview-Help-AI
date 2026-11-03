#!/bin/bash
# v2.1 체크리스트 재채점 — WSL 세션을 붙잡은 채로 실행하고, 완료·실패 시에만 한 줄 출력한다. 중단 후 재실행하면 이어서 한다.
#   bash run_relabel.sh           : 전체 (이어서)
#   bash run_relabel.sh --trial   : 앞의 70개(조합 10개)만 시험 → 결과는 지우고 다시 시작 가능
SRC=/mnt/c/Users/Owner/Desktop/Interview-Help-AI/backend/training
cd ~/llama-train
cp $SRC/generate_teacher_scores.py $SRC/relabel_checklist.py .
LOG=relabel_v21.log
ARGS=""
if [ "$1" = "--trial" ]; then rm -f data/score_teacher_qwen_v21.jsonl; LOG=relabel_trial.log; rm -f $LOG; ARGS="--limit 70"; fi
~/venvs/llama-finetune/bin/python relabel_checklist.py $ARGS >> $LOG 2>&1
code=$?
if grep -q RELABEL_DONE $LOG && [ $code -eq 0 ]; then
  echo "RELABEL_DONE: $(wc -l < data/score_teacher_qwen_v21.jsonl)개, $(grep -o '파싱 실패 [0-9]*' $LOG | tail -n 1)"
else
  echo "RELABEL_FAILED (exit $code): $(tail -c 400 $LOG)"
fi
