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
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from trl import SFTConfig, SFTTrainer

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
    return parser.parse_args()


def load_model_and_tokenizer(args):
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    if tokenizer.pad_token is None:
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
        save_strategy="epoch",
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
    )

    trainer.train()

    trainer.model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(f"LoRA 어댑터 저장 완료: {args.output_dir}")


if __name__ == "__main__":
    main()
