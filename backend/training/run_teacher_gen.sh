#!/bin/bash
# 선생님 데이터(v2) 생성 — WSL 세션을 붙잡은 채로 실행하고, 완료·실패 시에만 한 줄 출력한다.
# 중간에 끊겨도 다시 실행하면 이미 만든 조합은 건너뛰고 이어서 생성한다.
#   bash run_teacher_gen.sh            : 전체 생성 (이어서)
#   bash run_teacher_gen.sh --fresh    : 처음부터 다시
#   bash run_teacher_gen.sh --trial    : 조합 2개만 시험 생성 (별도 로그)
SRC=/mnt/c/Users/Owner/Desktop/Interview-Help-AI/backend/training
DATA=data/score_teacher_qwen_v2.jsonl
cd ~/llama-train
cp $SRC/generate_teacher_scores.py $SRC/inspect_teacher.py .
LOG=teacher_gen_v2.log
ARGS="--rounds 2"
if [ "$1" = "--fresh" ]; then rm -f $DATA $LOG; fi
if [ "$1" = "--trial" ]; then rm -f $DATA; LOG=teacher_trial_v2.log; rm -f $LOG; ARGS="--rounds 2 --trial"; fi
~/venvs/llama-finetune/bin/python generate_teacher_scores.py $ARGS >> $LOG 2>&1
code=$?
if grep -q GENERATION_DONE $LOG && [ $code -eq 0 ]; then
  echo "GENERATION_DONE: $(wc -l < $DATA)개, 건너뜀 $(grep -c '건너뜀' $LOG)건"
else
  echo "GENERATION_FAILED (exit $code): $(tail -c 400 $LOG)"
fi
