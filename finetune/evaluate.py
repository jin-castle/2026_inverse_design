"""
Fine-tuned MEEP 모델 평가 스크립트

실행:
  python finetune/evaluate.py \
    --model models/meep-coder-v1 \
    --test_data finetune_data/test.jsonl
"""
import argparse, json
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--test_data", default="finetune_data/test.jsonl")
    p.add_argument("--n_samples", type=int, default=20, help="평가할 샘플 수")
    p.add_argument("--base_model", default=None, help="비교용 기반 모델")
    return p.parse_args()


def load_model(model_path: str):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    base_model_name = json.load(open(f"{model_path}/adapter_config.json"))["base_model_name_or_path"]

    print(f"기반 모델 로딩: {base_model_name}")
    model = AutoModelForCausalLM.from_pretrained(
        base_model_name, device_map="auto", torch_dtype=torch.bfloat16
    )
    model = PeftModel.from_pretrained(model, model_path)
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    return model, tokenizer


def generate(model, tokenizer, prompt: str, max_new_tokens=512) -> str:
    import torch
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.1,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    new_tokens = outputs[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True)


def evaluate(args):
    model, tokenizer = load_model(args.model)

    # 테스트 데이터 로드
    test_data = []
    with open(args.test_data, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                test_data.append(json.loads(line))

    # 샘플링
    import random
    random.seed(42)
    samples = random.sample(test_data, min(args.n_samples, len(test_data)))

    results = []
    for i, ex in enumerate(samples):
        # 프롬프트 구성 (output 제외)
        instruction = ex["instruction"]
        inp = ex.get("input", "")
        if inp:
            prompt = f"### 지시사항:\n{instruction}\n\n### 입력:\n{inp}\n\n### 응답:\n"
        else:
            prompt = f"### 지시사항:\n{instruction}\n\n### 응답:\n"

        expected = ex.get("output", "")
        predicted = generate(model, tokenizer, prompt)

        # 간단한 품질 지표
        has_korean = any('\uac00' <= c <= '\ud7a3' for c in predicted)
        has_code = "```" in predicted or "def " in predicted
        is_relevant = any(kw in predicted.lower() for kw in
                         ["meep", "mp.", "simulation", "source", "pml", "eig"])

        results.append({
            "input_preview": inp[:100],
            "expected_preview": expected[:150],
            "predicted_preview": predicted[:200],
            "has_korean": has_korean,
            "has_code": has_code,
            "is_relevant": is_relevant,
        })

        print(f"\n[{i+1}/{len(samples)}]")
        print(f"  입력: {inp[:80]}...")
        print(f"  예상: {expected[:100]}...")
        print(f"  생성: {predicted[:150]}...")
        print(f"  품질: 한국어={has_korean}, 코드포함={has_code}, MEEP관련={is_relevant}")

    # 통계 출력
    n = len(results)
    print(f"\n\n=== 평가 결과 ({n}개 샘플) ===")
    print(f"  한국어 응답률:  {sum(r['has_korean'] for r in results)/n*100:.0f}%")
    print(f"  코드 포함률:    {sum(r['has_code'] for r in results)/n*100:.0f}%")
    print(f"  MEEP 관련성:    {sum(r['is_relevant'] for r in results)/n*100:.0f}%")

    # 결과 저장
    out_path = Path(args.model) / "eval_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out_path}")


if __name__ == "__main__":
    evaluate(parse_args())
