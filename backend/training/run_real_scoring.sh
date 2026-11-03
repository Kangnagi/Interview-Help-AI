#!/bin/bash
# A1: 실제 면접 답변 채점 — WSL 세션을 붙잡은 채로 실행하고, 완료·실패 시에만 한 줄 출력한다. 재실행하면 이어서 한다.
#   bash run_real_scoring.sh           : 전체 (처음 실행 시 real_pool.jsonl도 만든다)
#   bash run_real_scoring.sh --trial   : 앞의 20개만 시험
SRC=/mnt/c/Users/Owner/Desktop/Interview-Help-AI/backend/training
DESKTOP_DATA=/mnt/c/Users/Owner/Desktop/llama-finetune/llama-finetune/training
PY=~/venvs/llama-finetune/bin/python
cd ~/llama-train
cp $SRC/generate_teacher_scores.py $SRC/relabel_checklist.py $SRC/build_real_pool.py $SRC/score_real_pool.py .
[ -f data/real_pool.jsonl ] || $PY build_real_pool.py --src $DESKTOP_DATA
LOG=real_scoring.log
# 실제 답변은 길어서(평균 450자) 10개에 약 1.4분 — 2,400개 전부는 5시간이 넘어 앞에서부터 LIMIT개만 채점한다
ARGS="--limit ${LIMIT:-1200}"
if [ "$1" = "--trial" ]; then rm -f data/score_teacher_real.jsonl; LOG=real_scoring_trial.log; rm -f $LOG; ARGS="--limit 20"; fi
$PY score_real_pool.py $ARGS >> $LOG 2>&1
code=$?
if grep -q REAL_SCORING_DONE $LOG && [ $code -eq 0 ]; then
  echo "REAL_SCORING_DONE: $(wc -l < data/score_teacher_real.jsonl)개, $(grep -o '실패 [0-9]*' $LOG | tail -n 1)"
else
  echo "REAL_SCORING_FAILED (exit $code): $(tail -c 400 $LOG)"
fi
