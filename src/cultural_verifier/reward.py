"""Skywork reward-model adapter used by the Best-of-4 experiment."""

from __future__ import annotations


class SkyworkRewardModel:
    def __init__(
        self,
        model_name: str = "Skywork/Skywork-Reward-V2-Qwen3-0.6B",
        *,
        max_length: int = 4096,
        device: str = "auto",
    ):
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("Install the reward extra: python -m pip install -e '.[reward]'") from exc

        self.torch = torch
        if device == "auto":
            if torch.backends.mps.is_available():
                device = "mps"
            elif torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"
        self.device = torch.device(device)
        self.max_length = max_length
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        dtype = torch.float16 if self.device.type in {"mps", "cuda"} else torch.float32
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            torch_dtype=dtype,
            low_cpu_mem_usage=True,
            num_labels=1,
        ).to(self.device)
        self.model.eval()

    def score(self, prompt_text: str, response_text: str) -> float:
        messages = [
            {"role": "user", "content": prompt_text},
            {"role": "assistant", "content": response_text},
        ]
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False,
        )
        if self.tokenizer.bos_token and text.startswith(self.tokenizer.bos_token):
            text = text[len(self.tokenizer.bos_token) :]
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=self.max_length,
        )
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        with self.torch.inference_mode():
            score = self.model(**inputs).logits.squeeze().float().cpu().item()
        return float(score)
