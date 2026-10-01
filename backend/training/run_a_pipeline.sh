#!/bin/bash
# A1 → A2 전체 파이프라인. 몇 번을 다시 실행해도 끝난 단계는 건너뛰고 남은 단계부터 이어서 한다.
#   ① 실제 답변 채점(A1)  ② 데이터 합치기  ③ a12 학습(바탕화면 모델에서 출발)  ④ a1 학습(비교용)  ⑤ 비교 평가
# 단계가 끝날 때마다 STEP_DONE, 전부 끝나면 PIPELINE_DONE, 실패하면 PIPELINE_FAILED 한 줄만 출력한다.
SRC=/mnt/c/Users/Owner/Desktop/Interview-Help-AI/backend/training
cd ~/llama-train
fail() { echo "PIPELINE_FAILED at $1: $2"; exit 1; }

# ① A1 채점
n=$( [ -f data/score_teacher_real.jsonl ] && wc -l < data/score_teacher_real.jsonl || echo 0 )
if [ "$n" -lt "${LIMIT:-1200}" ]; then
  r=$(bash $SRC/run_real_scoring.sh); [[ "$r" == REAL_SCORING_DONE* ]] || fail scoring "$r"
  echo "STEP_DONE scoring: $r"
fi

# ② 데이터 합치기 (채점 결과가 합친 파일보다 새로우면 다시)
if [ ! -f data/mix_train.jsonl ] || [ data/score_teacher_real.jsonl -nt data/mix_train.jsonl ]; then
  r=$(bash $SRC/run_mix_train.sh build); [[ "$r" == 학습* ]] || fail build "$r"
  echo "STEP_DONE build: $r"
fi

# ③④ 학습 — 끝난 모델은 건너뛰고, 체크포인트가 있으면 이어서
for NAME in a12 a1; do
  OUT=output/llama-3.2-3b-score-$NAME
  [ -f $OUT/adapter_model.safetensors ] && continue
  RES=""; ls -d $OUT/checkpoint-* >/dev/null 2>&1 && RES="--resume"
  r=$(bash $SRC/run_mix_train.sh train $NAME $RES); [[ "$r" == TRAIN_DONE* ]] || fail "train $NAME" "$r"
  echo "STEP_DONE $r"
done

# ⑤ 비교 평가 — 모델별, 끝난 것은 건너뜀
for A in a12 a1 v21; do
  grep -q "===== EVAL_END" eval_mix_$A.log 2>/dev/null && continue
  r=$(bash $SRC/run_mix_train.sh eval $A); [[ "$r" == EVAL_DONE* ]] || fail "eval $A" "$r"
  echo "STEP_DONE $r"
done
echo "PIPELINE_DONE"
