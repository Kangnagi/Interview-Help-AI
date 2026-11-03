"""
Llama-3.2-3B-Instruct QLoRA 파인튜닝 스크립트

AI 면접 도우미(Interview-Help-AI)의 면접 질문 생성 / 답변 피드백 모델을 파인튜닝합니다.
4bit(QLoRA) 양자화로 8B 모델에서 발생하던 CUDA OOM 문제를 피하고,
가벼운 3B 모델로 동일한 파이프라인을 재사용할 수 있도록 구성했습니다.

사용 예:
    python training/finetune_llama.py \
        --data_path training/data/sample_dataset.jsonl \
        --output_dir training/output/llama-3.2-3b-interview
"""

import argparse
import os

import torch
from datasets import load_dataset
from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from trl import DataCollatorForCompletionOnlyLM, SFTConfig, SFTTrainer

# Llama 3 대화 형식에서 모델 답변이 시작되는 표시 — --completion_only일 때 이 뒤(답변)만 손실을 계산한다
ASSISTANT_HEADER = "<|start_header_id|>assistant<|end_header_id|>\n\n"

DEFAULT_MODEL = "meta-llama/Llama-3.2-3B-Instruct"


def parse_args():
    parser = argparse.ArgumentParser(description="Llama-3.2-3B-Instruct QLoRA 파인튜닝")
    parser.add_argument("--model_name", default=DEFAULT_MODEL, help="HuggingFace 모델 ID")
    parser.add_argument("--data_path", default="training/data/sample_dataset.jsonl")
    parser.add_argument("--output_dir", default="training/output/llama-3.2-3b-interview")
    parser.add_argument("--num_train_epochs", type=float, default=3)
    parser.add_argument("--per_device_train_batch_size", type=int, default=2)
    parser.add_argument("--gradient_accumulation_steps", type=int, default=8)
    parser.add_argument("--learning_rate", type=float, default=2e-4)
    parser.add_argument("--max_seq_length", type=int, default=1024)
    parser.add_argument("--lora_r", type=int, default=16)
    parser.add_argument("--lora_alpha", type=int, default=32)
    parser.add_argument("--lora_dropout", type=float, default=0.05)
    parser.add_argument(
        "--no_4bit",
        action="store_true",
        help="4bit 양자화를 끄고 bf16/fp16으로 로드합니다 (VRAM 여유가 있을 때만 사용)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume", action="store_true", help="output_dir의 마지막 체크포인트부터 이어서 학습")
    parser.add_argument(
        "--init_adapter",
        default=None,
        help="이미 학습된 LoRA 어댑터에서 출발해 이어서 학습 (예: 바탕화면 llama-finetune의 best). "
             "지정하면 --lora_r/--lora_alpha 대신 그 어댑터의 설정을 그대로 쓴다.",
    )
    parser.add_argument("--completion_only", action="store_true",
                        help="답변(assistant) 부분만 학습 — 입력이 길고 답이 짧은 과제(질문 생성)용. "
                             "끄면 예전처럼 입력까지 전체 문장을 학습한다 (채점 어댑터 a1~b3는 이 방식)")
    parser.add_argument("--save_steps", type=int, default=0,
                        help="0이면 에포크마다 저장, 양수면 N 스텝마다 저장 (긴 학습이 중간에 끊겨도 --resume으로 이어가기 위함)")
    return parser.parse_args()


def load_model_and_tokenizer(args):
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    if tokenizer.pad_token is None:
        # --completion_only의 데이터 정리기는 패딩 토큰의 정답을 지운다 — 패딩을 문장 끝(<|eot_id|>)과 같게 두면
        # 답변 끝 토큰까지 지워져 모델이 답을 끝내는 법을 못 배운다 → Llama 3의 예약 패딩 토큰을 쓴다
        reserved_pad = "<|finetune_right_pad_id|>"
        if args.completion_only and tokenizer.convert_tokens_to_ids(reserved_pad) != tokenizer.unk_token_id:
            tokenizer.pad_token = reserved_pad
        else:
            tokenizer.pad_token = tokenizer.eos_token

    compute_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16

    quantization_config = None
    if not args.no_4bit:
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=compute_dtype,
            bnb_4bit_use_double_quant=True,
        )

    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        quantization_config=quantization_config,
        torch_dtype=compute_dtype,
        device_map="auto",
    )
    model.config.use_cache = False

    if quantization_config is not None:
        model = prepare_model_for_kbit_training(model)

    return model, tokenizer


def build_formatting_func(tokenizer):
    def formatting_func(example):
        return tokenizer.apply_chat_template(
            example["messages"], tokenize=False, add_generation_prompt=False
        )

    return formatting_func


def main():
    args = parse_args()
    torch.manual_seed(args.seed)

    if not os.path.exists(args.data_path):
        raise FileNotFoundError(
            f"데이터셋을 찾을 수 없습니다: {args.data_path}\n"
            "training/data/sample_dataset.jsonl 을 참고해 같은 형식(messages: [{role, content}, ...])으로 "
            "자체 데이터를 준비하세요."
        )

    dataset = load_dataset("json", data_files=args.data_path, split="train")

    model, tokenizer = load_model_and_tokenizer(args)

    if args.init_adapter:
        # 기존 어댑터 가중치에서 출발 — 그 어댑터가 배운 것(예: 실제 면접 답변 피드백)을 유지한 채 새 과제를 추가로 배운다
        model = PeftModel.from_pretrained(model, args.init_adapter, is_trainable=True)
        print(f"기존 어댑터에서 이어서 학습: {args.init_adapter}")
    else:
        lora_config = LoraConfig(
            r=args.lora_r,
            lora_alpha=args.lora_alpha,
            lora_dropout=args.lora_dropout,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=[
                "q_proj", "k_proj", "v_proj", "o_proj",
                "gate_proj", "up_proj", "down_proj",
            ],
        )
        model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    bf16_ok = torch.cuda.is_available() and torch.cuda.is_bf16_supported()

    sft_config = SFTConfig(
        output_dir=args.output_dir,
        num_train_epochs=args.num_train_epochs,
        per_device_train_batch_size=args.per_device_train_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        gradient_checkpointing=True,
        learning_rate=args.learning_rate,
        optim="paged_adamw_8bit" if not args.no_4bit else "adamw_torch",
        logging_steps=10,
        save_strategy="steps" if args.save_steps > 0 else "epoch",
        save_steps=args.save_steps if args.save_steps > 0 else 500,
        save_total_limit=3,
        bf16=bf16_ok,
        fp16=not bf16_ok,
        max_seq_length=args.max_seq_length,
        packing=False,
        report_to="none",
        seed=args.seed,
    )

    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=dataset,
        formatting_func=build_formatting_func(tokenizer),
        data_collator=DataCollatorForCompletionOnlyLM(
            tokenizer(ASSISTANT_HEADER, add_special_tokens=False).input_ids, tokenizer=tokenizer
        ) if args.completion_only else None,
    )

    trainer.train(resume_from_checkpoint=args.resume or None)

    trainer.model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(f"LoRA 어댑터 저장 완료: {args.output_dir}")


if __name__ == "__main__":
    main()
