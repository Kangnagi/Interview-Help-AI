#!/bin/bash
# 선생님 데이터 전체 생성 — WSL 세션을 붙잡은 채로 실행하고, 완료·실패 시에만 한 줄 출력한다.
# 중간에 끊겨도 다시 실행하면 이미 만든 조합은 건너뛰고 이어서 생성한다.
cd ~/llama-train
cp /mnt/c/Users/Owner/Desktop/Interview-Help-AI/backend/training/generate_teacher_scores.py .
if [ "$1" = "--fresh" ]; then rm -f data/score_teacher_qwen.jsonl teacher_gen.log; fi
~/venvs/llama-finetune/bin/python generate_teacher_scores.py --rounds 2 >> teacher_gen.log 2>&1
code=$?
if grep -q GENERATION_DONE teacher_gen.log && [ $code -eq 0 ]; then
  echo "GENERATION_DONE: $(wc -l < data/score_teacher_qwen.jsonl)개, 건너뜀 $(grep -c '건너뜀' teacher_gen.log)건"
else
  echo "GENERATION_FAILED (exit $code): $(tail -c 400 teacher_gen.log)"
fi
