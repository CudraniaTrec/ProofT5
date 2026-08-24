from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class GenerationResult:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class ModelClient(Protocol):
    model_name: str

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
        top_p: float,
        seed: int,
    ) -> GenerationResult: ...


class OpenAICompatibleClient:
    def __init__(self, base_url: str, model_name: str, api_key_env: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.api_key_env = api_key_env

    def generate(self, messages, *, max_tokens, temperature, top_p, seed):
        payload = json.dumps(
            {
                "model": self.model_name,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "seed": seed,
            }
        ).encode()
        headers = {"Content-Type": "application/json"}
        api_key = os.environ.get(self.api_key_env, "") if self.api_key_env else ""
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        request = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=payload,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=600) as response:
            body = json.load(response)
        usage = body.get("usage", {})
        return GenerationResult(
            body["choices"][0]["message"]["content"],
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
        )


class ScriptedClient:
    """Deterministic no-model backend used for pipeline tests and dry pilots."""

    def __init__(self, path: Path) -> None:
        self.model_name = f"scripted:{path}"
        values = json.loads(path.read_text())
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise ValueError("scripted responses must be a JSON list of strings")
        self.values = iter(values)

    def generate(self, messages, *, max_tokens, temperature, top_p, seed):
        del messages, max_tokens, temperature, top_p, seed
        try:
            return GenerationResult(next(self.values))
        except StopIteration as exc:
            raise RuntimeError("scripted response file was exhausted") from exc


class HuggingFaceClient:
    def __init__(
        self,
        model_name: str,
        device: str,
        dtype: str,
        local_files_only: bool,
    ) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        self.model_name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name, local_files_only=local_files_only, trust_remote_code=True
        )
        torch_dtype = {
            "auto": "auto",
            "bf16": torch.bfloat16,
            "fp16": torch.float16,
            "fp32": torch.float32,
        }[dtype]
        kwargs = {
            "local_files_only": local_files_only,
            "trust_remote_code": True,
            "torch_dtype": torch_dtype,
        }
        if device == "auto":
            kwargs["device_map"] = "auto"
        self.model = AutoModelForCausalLM.from_pretrained(model_name, **kwargs).eval()
        if device != "auto":
            self.model.to(device)
        self.device = next(self.model.parameters()).device

    def generate(self, messages, *, max_tokens, temperature, top_p, seed):
        torch = self.torch
        torch.manual_seed(seed)
        if getattr(self.tokenizer, "chat_template", None):
            inputs = self.tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,
                return_tensors="pt",
                return_dict=True,
            )
        else:
            inputs = self.tokenizer(
                "\n\n".join(message["content"] for message in messages),
                return_tensors="pt",
            )
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        do_sample = temperature > 0
        output = self.model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            do_sample=do_sample,
            temperature=max(temperature, 1e-5) if do_sample else None,
            top_p=top_p if do_sample else None,
            pad_token_id=(
                self.tokenizer.pad_token_id
                if self.tokenizer.pad_token_id is not None
                else self.tokenizer.eos_token_id
            ),
        )
        prompt_length = inputs["input_ids"].shape[-1]
        completion = output[0, prompt_length:]
        return GenerationResult(
            self.tokenizer.decode(completion, skip_special_tokens=True),
            int(prompt_length),
            int(completion.shape[-1]),
        )


def build_client(args) -> ModelClient:
    if args.backend == "openai":
        return OpenAICompatibleClient(args.base_url, args.model, args.api_key_env)
    if args.backend == "hf":
        return HuggingFaceClient(
            args.model, args.device, args.dtype, args.local_files_only
        )
    if args.backend == "scripted":
        return ScriptedClient(Path(args.scripted_responses))
    raise ValueError(args.backend)


def add_model_client_arguments(parser) -> None:
    parser.add_argument("--backend", choices=["hf", "openai", "scripted"], default="hf")
    parser.add_argument("--model", default="")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--dtype", choices=["auto", "bf16", "fp16", "fp32"], default="bf16")
    parser.add_argument("--local_files_only", action="store_true")
    parser.add_argument("--base_url", default="http://127.0.0.1:8000")
    parser.add_argument("--api_key_env", default="OPENAI_API_KEY")
    parser.add_argument("--scripted_responses", default="")
