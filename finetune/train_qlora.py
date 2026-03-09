"""
MEEP 특화 QLoRA Fine-tuning 스크립트
======================================
기반 모델: Qwen2.5-Coder-7B-Instruct (권장) 또는 Llama-3.2-3B

실행 (SimServer):
  python finetune/train_qlora.py \
    --base_model Qwen/Qwen2.5-Coder-7B-Instruct \
    --data finetune_data/train.jsonl \
    --output_dir models/meep-coder-v1

의존성:
  pip install transformers datasets peft trl bitsandbytes accelerate
  pip install unsloth  # 2배 빠른 학습 (선택)
"""
import argparse, json
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--base_model",  default="Qwen/Qwen2.5-Coder-7B-Instruct")
    p.add_argument("--data",        default="finetune_data/train.jsonl")
    p.add_argument("--output_dir",  default="models/meep-coder-v1")
    p.add_argument("--num_epochs",  type=int, default=3)
    p.add_argument("--batch_size",  type=int, default=4)
    p.add_argument("--grad_accum",  type=int, default=4)  # effective batch = 16
    p.add_argument("--lr",          type=float, default=2e-4)
    p.add_argument("--lora_rank",   type=int, default=16)
    p.add_argument("--lora_alpha",  type=int, default=32)
    p.add_argument("--max_seq_len", type=int, default=2048)
    p.add_argument("--load_in_4bit", action="store_true", default=True)
    p.add_argument("--use_unsloth", action="store_true", default=False)
    return p.parse_args()


def load_dataset(data_path: str):
    """JSONL → HuggingFace Dataset"""
    from datasets import Dataset
    records = []
    with open(data_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return Dataset.from_list(records)


def format_prompt(example: dict) -> str:
    """Alpaca 형식 프롬프트"""
    instruction = example["instruction"]
    inp = example.get("input", "").strip()
    output = example.get("output", "").strip()

    if inp:
        prompt = (
            f"### 지시사항:\n{instruction}\n\n"
            f"### 입력:\n{inp}\n\n"
            f"### 응답:\n{output}"
        )
    else:
        prompt = (
            f"### 지시사항:\n{instruction}\n\n"
            f"### 응답:\n{output}"
        )
    return prompt


def train_with_trl(args):
    """TRL SFTTrainer 사용 (표준 방법)"""
    import torch
    from transformers import (
        AutoModelForCausalLM, AutoTokenizer,
        BitsAndBytesConfig, TrainingArguments,
    )
    from peft import LoraConfig, get_peft_model, TaskType
    from trl import SFTTrainer, SFTConfig

    print(f"모델 로딩: {args.base_model}")
    print(f"GPU 메모리: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}GB")

    # ── 4bit 양자화 설정 (QLoRA 핵심) ────────────────────────────────────────
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",         # NormalFloat4 (QLoRA 논문 권장)
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,    # 메모리 추가 절감
    ) if args.load_in_4bit else None

    # ── 모델 로드 ────────────────────────────────────────────────────────────
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(
        args.base_model,
        trust_remote_code=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # ── LoRA 설정 ────────────────────────────────────────────────────────────
    # target_modules: attention 레이어 행렬들 (모델마다 이름이 다름)
    lora_config = LoraConfig(
        r=args.lora_rank,           # rank: 낮을수록 적은 파라미터, 높을수록 표현력 증가
        lora_alpha=args.lora_alpha, # scaling factor = alpha/rank
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",  # attention
            "gate_proj", "up_proj", "down_proj",       # MLP
        ],
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )

    # ── 데이터 로드 ───────────────────────────────────────────────────────────
    dataset = load_dataset(args.data)
    print(f"학습 데이터: {len(dataset)}개")

    # ── 학습 설정 ────────────────────────────────────────────────────────────
    training_args = SFTConfig(
        output_dir=args.output_dir,
        num_train_epochs=args.num_epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        bf16=True,               # A100에서 bfloat16 사용
        fp16=False,
        logging_steps=10,
        save_steps=200,
        save_total_limit=3,
        max_seq_length=args.max_seq_len,
        report_to="none",        # wandb 쓰려면 "wandb"로 변경
        optim="paged_adamw_32bit",  # QLoRA 권장 optimizer
    )

    # ── SFT 트레이너 ─────────────────────────────────────────────────────────
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        peft_config=lora_config,
        args=training_args,
        formatting_func=format_prompt,
    )

    print("학습 시작...")
    print(f"  Epochs: {args.num_epochs}")
    print(f"  Batch size: {args.batch_size} x grad_accum {args.grad_accum} = {args.batch_size * args.grad_accum}")
    print(f"  LoRA rank: {args.lora_rank}, alpha: {args.lora_alpha}")
    print(f"  학습 가능 파라미터: {sum(p.numel() for p in model.parameters() if p.requires_grad):,}")

    trainer.train()

    # ── 저장 ────────────────────────────────────────────────────────────────
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(f"\n모델 저장 완료: {args.output_dir}")
    print("다음 단계: python finetune/evaluate.py --model " + args.output_dir)


def train_with_unsloth(args):
    """Unsloth 사용 (2배 빠름, A100 권장)"""
    from unsloth import FastLanguageModel
    import torch

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base_model,
        max_seq_length=args.max_seq_len,
        dtype=torch.bfloat16,
        load_in_4bit=args.load_in_4bit,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_rank,
        lora_alpha=args.lora_alpha,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0,       # Unsloth에서는 0 권장
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    from trl import SFTTrainer, SFTConfig
    dataset = load_dataset(args.data)

    training_args = SFTConfig(
        output_dir=args.output_dir,
        num_train_epochs=args.num_epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        bf16=True,
        logging_steps=10,
        save_steps=200,
        max_seq_length=args.max_seq_len,
        optim="adamw_8bit",
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=training_args,
        formatting_func=format_prompt,
    )

    trainer.train()
    model.save_pretrained_merged(args.output_dir, tokenizer, save_method="merged_16bit")
    print(f"모델 저장: {args.output_dir}")


if __name__ == "__main__":
    args = parse_args()
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    if args.use_unsloth:
        print("Unsloth 모드 (빠른 학습)")
        train_with_unsloth(args)
    else:
        print("TRL SFTTrainer 모드 (표준)")
        train_with_trl(args)
