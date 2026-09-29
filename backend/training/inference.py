"""
파인튜닝된 Llama-3.2-3B-Instruct LoRA 어댑터로 추론(테스트)하는 스크립트

사용 예:
    python training/inference.py \
        --adapter_dir training/output/llama-3.2-3b-interview \
        --prompt "자기소개서: ... 면접 질문 2개를 생성해주세요."
"""

import argparse

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

DEFAULT_MODEL = "meta-llama/Llama-3.2-3B-Instruct"


def parse_args():
    parser = argparse.ArgumentParser(description="파인튜닝 모델 추론 테스트")
    parser.add_argument("--base_model", default=DEFAULT_MODEL)
    parser.add_argument("--adapter_dir", required=True, help="finetune_llama.py의 --output_dir 경로")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--max_new_tokens", type=int, default=512)
    parser.add_argument("--no_4bit", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    compute_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16

    quantization_config = None
    if not args.no_4bit:
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=compute_dtype,
            bnb_4bit_use_double_quant=True,
        )

    tokenizer = AutoTokenizer.from_pretrained(args.adapter_dir)
    base_model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        quantization_config=quantization_config,
        torch_dtype=compute_dtype,
        device_map="auto",
    )
    model = PeftModel.from_pretrained(base_model, args.adapter_dir)
    model.eval()

    messages = [
        {"role": "system", "content": "당신은 AI 면접 도우미입니다."},
        {"role": "user", "content": args.prompt},
    ]
    inputs = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, return_tensors="pt"
    ).to(model.device)

    with torch.no_grad():
        output = model.generate(
            inputs,
            max_new_tokens=args.max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
        )

    response = tokenizer.decode(output[0][inputs.shape[-1]:], skip_special_tokens=True)
    print(response)


if __name__ == "__main__":
    main()
