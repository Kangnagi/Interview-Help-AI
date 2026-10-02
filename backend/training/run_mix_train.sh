#!/bin/bash
# A1+A2 학습·평가 — 완료·실패 시에만 한 줄 출력. 중간에 끊기면 같은 명령에 --resume을 붙여 이어서 학습한다.
#   bash run_mix_train.sh build            : 합성+실제 데이터 합치기 (mix_train / teacher_eval / real_eval)
#   bash run_mix_train.sh train a12 [--resume] : 바탕화면 모델(best)에서 출발해 학습 (A1+A2)
#   bash run_mix_train.sh train a1  [--resume] : 기본 모델에서 새로 학습 (A1만, 비교용)
#   bash run_mix_train.sh train b1  [--resume] : Bllossom-3B(한국어 Llama)에서 a1과 같은 데이터·설정으로 학습
#   bash run_mix_train.sh eval v21|a1|a12|b1  : 같은 평가셋(합성·실제)과 프로브로 평가 → eval_mix_<이름>.log
SRC=/mnt/c/Users/Owner/Desktop/Interview-Help-AI/backend/training
DESKTOP_ADAPTER=/mnt/c/Users/Owner/Desktop/llama-finetune/llama-finetune/training/output/llama-3.2-3b-interview/best
BLLOSSOM=~/models/llama-3.2-Korean-Bllossom-3B   # Windows HF 캐시에서 복사해 둔 Bllossom-3B
PY=~/venvs/llama-finetune/bin/python
cd ~/llama-train
cp $SRC/finetune_llama.py $SRC/build_mix_dataset.py $SRC/eval_score_adapter.py $SRC/probe_score_range.py .
# 이름이 b로 시작하면 Bllossom 위에서 학습·평가 (그 외는 기본 Llama-3.2-3B)
BASE_ARGS=""; [[ "$2" == b* ]] && BASE_ARGS="--base_model $BLLOSSOM"

if [ "$1" = "build" ]; then
  $PY build_mix_dataset.py 2>&1 | tail -n 1
elif [ "$1" = "train" ]; then
  NAME=$2; OUT=output/llama-3.2-3b-score-$NAME; LOG=train_$NAME.log
  INIT=""; [ "$NAME" = "a12" ] && INIT="--init_adapter $DESKTOP_ADAPTER"
  [[ "$NAME" == b* ]] && INIT="--model_name $BLLOSSOM"
  [ "$3" = "--resume" ] || rm -f $LOG
  $PY finetune_llama.py --data_path data/mix_train.jsonl --output_dir $OUT $INIT \
    --num_train_epochs 3 --per_device_train_batch_size 2 --gradient_accumulation_steps 4 \
    --save_steps 100 $3 >> $LOG 2>&1
  code=$?
  if grep -q "저장 완료" $LOG && [ $code -eq 0 ]; then
    echo "TRAIN_DONE $NAME: $(tr '\r' '\n' < $LOG | grep -o "'train_runtime': [0-9.]*" | tail -n 1)"
  else
    echo "TRAIN_FAILED $NAME (exit $code): $(tr '\r' '\n' < $LOG | tail -c 300)"
  fi
elif [ "$1" = "eval" ]; then
  # 모델별로 따로 평가·저장 (30분 구간에 끊겨도 끝난 모델은 다시 하지 않도록)
  A=$2; D=output/llama-3.2-3b-score-$A; ELOG=eval_mix_$A.log
  [ -d $D ] || { echo "EVAL_FAILED $A: 어댑터 없음"; exit 1; }
  {
    echo "===== $A — 합성 평가셋"; $PY eval_score_adapter.py --adapter_dir $D --eval_path data/teacher_eval.jsonl $BASE_ARGS
    echo "===== $A — 실제 답변 평가셋"; $PY eval_score_adapter.py --adapter_dir $D --eval_path data/real_eval.jsonl $BASE_ARGS
    echo "===== $A — 프로브"; $PY probe_score_range.py --adapter_dir $D $BASE_ARGS
    echo "===== EVAL_END"
  } > $ELOG 2>&1
  cp $ELOG $SRC/$ELOG
  grep -q "===== EVAL_END" $ELOG && echo "EVAL_DONE $A" || echo "EVAL_FAILED $A: $(tail -c 300 $ELOG)"
fi
