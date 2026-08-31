from __future__ import annotations

import json
import os
import re
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
        stop_strings: list[str] | None = None,
        stop_at_java_class: bool = False,
    ) -> GenerationResult: ...


class OpenAICompatibleClient:
    def __init__(self, base_url: str, model_name: str, api_key_env: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.api_key_env = api_key_env

    def generate(
        self,
        messages,
        *,
        max_tokens,
        temperature,
        top_p,
        seed,
        stop_strings=None,
        stop_at_java_class=False,
    ):
        del stop_strings, stop_at_java_class
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

    def generate(
        self,
        messages,
        *,
        max_tokens,
        temperature,
        top_p,
        seed,
        stop_strings=None,
        stop_at_java_class=False,
    ):
        del messages, max_tokens, temperature, top_p, seed, stop_strings, stop_at_java_class
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
        tokenizer_name: str = "",
        model_family: str = "auto",
        seq2seq_prompt_mode: str = "last_user",
        use_chat_template: bool = True,
    ) -> None:
        from .hf_runtime import load_hf_runtime

        self.model_name = model_name
        runtime = load_hf_runtime(
            model_path=model_name,
            tokenizer_path=tokenizer_name,
            device=device,
            dtype=dtype,
            local_files_only=local_files_only,
            model_family=model_family,
        )
        self.torch = runtime.torch
        self.tokenizer = runtime.tokenizer
        self.model = runtime.model
        self.device = runtime.device
        self.model_family = runtime.family
        self.seq2seq_prompt_mode = seq2seq_prompt_mode
        self.use_chat_template = use_chat_template

    def generate(
        self,
        messages,
        *,
        max_tokens,
        temperature,
        top_p,
        seed,
        stop_strings=None,
        stop_at_java_class=False,
    ):
        torch = self.torch
        torch.manual_seed(seed)
        if self.model_family == "seq2seq":
            text = (
                messages[-1]["content"]
                if self.seq2seq_prompt_mode == "last_user"
                else "\n\n".join(message["content"] for message in messages)
            )
            inputs = self.tokenizer(
                text, return_tensors="pt", max_length=1024, truncation=True
            )
        elif self.use_chat_template and getattr(self.tokenizer, "chat_template", None):
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
        generation_kwargs = {}
        if stop_strings or stop_at_java_class:
            from transformers import StoppingCriteria, StoppingCriteriaList

            prompt_length = inputs["input_ids"].shape[-1]
            tokenizer = self.tokenizer

            def brace_delta(text):
                depth = 0
                index = 0
                state = "code"
                while index < len(text):
                    char = text[index]
                    nxt = text[index + 1] if index + 1 < len(text) else ""
                    if state == "line_comment":
                        if char == "\n":
                            state = "code"
                    elif state == "block_comment":
                        if char == "*" and nxt == "/":
                            state = "code"
                            index += 1
                    elif state in {"string", "char"}:
                        if char == "\\":
                            index += 1
                        elif (state == "string" and char == '"') or (
                            state == "char" and char == "'"
                        ):
                            state = "code"
                    else:
                        if char == "/" and nxt == "/":
                            state = "line_comment"
                            index += 1
                        elif char == "/" and nxt == "*":
                            state = "block_comment"
                            index += 1
                        elif char == '"':
                            state = "string"
                        elif char == "'":
                            state = "char"
                        elif char == "{":
                            depth += 1
                        elif char == "}":
                            depth -= 1
                    index += 1
                return depth

            class StopOnStrings(StoppingCriteria):
                def __call__(self, input_ids, scores, **kwargs):
                    del scores, kwargs
                    generated_text = tokenizer.decode(
                        input_ids[0, prompt_length:], skip_special_tokens=False
                    )
                    if stop_strings:
                        for marker in stop_strings:
                            position = generated_text.find(marker)
                            if position < 0:
                                continue
                            # Few-shot Base models can copy the instruction
                            # header before solving.  Stop only when that
                            # header reappears after a completed Java class.
                            if marker.startswith("\nComplete the following") and "}" not in generated_text[:position]:
                                continue
                            return True
                    if stop_at_java_class:
                        generated_matches = list(
                            re.finditer(
                                r"\b(?:public\s+)?class\s+[A-Za-z_$][A-Za-z0-9_$]*\s*\{",
                                generated_text,
                            )
                        )
                        if generated_matches:
                            generated_class = generated_text[generated_matches[0].start() :]
                            if "}" in generated_class and brace_delta(generated_class) == 0:
                                return True
                        prefix_text = tokenizer.decode(
                            input_ids[0, :prompt_length], skip_special_tokens=False
                        )
                        matches = list(
                            re.finditer(
                                r"\b(?:public\s+)?class\s+[A-Za-z_$][A-Za-z0-9_$]*\s*\{",
                                prefix_text,
                            )
                        )
                        if matches:
                            prefix_segment = prefix_text[matches[-1].start() :]
                            base_depth = brace_delta(prefix_segment)
                            if base_depth > 0 and "}" in generated_text:
                                return base_depth + brace_delta(generated_text) <= 0
                    return False

            generation_kwargs["stopping_criteria"] = StoppingCriteriaList(
                [StopOnStrings()]
            )
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
            **generation_kwargs,
        )
        prompt_length = inputs["input_ids"].shape[-1]
        completion = (
            output[0]
            if self.model_family == "seq2seq"
            else output[0, prompt_length:]
        )
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
            args.model,
            args.device,
            args.dtype,
            args.local_files_only,
            args.tokenizer,
            args.model_family,
            args.hf_seq2seq_prompt_mode,
            use_chat_template=not getattr(args, "no_chat_template", False),
        )
    if args.backend == "scripted":
        return ScriptedClient(Path(args.scripted_responses))
    raise ValueError(args.backend)


def add_model_client_arguments(parser) -> None:
    parser.add_argument("--backend", choices=["hf", "openai", "scripted"], default="hf")
    parser.add_argument("--model", default="")
    parser.add_argument("--tokenizer", default="")
    parser.add_argument(
        "--model_family", choices=["auto", "causal", "seq2seq"], default="auto"
    )
    parser.add_argument(
        "--no_chat_template",
        action="store_true",
        help="Encode messages as plain concatenated text even when the tokenizer has a chat template.",
    )
    parser.add_argument(
        "--hf_seq2seq_prompt_mode",
        choices=["last_user", "joined_messages"],
        default="last_user",
    )
    parser.add_argument("--device", default="auto")
    parser.add_argument("--dtype", choices=["auto", "bf16", "fp16", "fp32"], default="bf16")
    parser.add_argument("--local_files_only", action="store_true")
    parser.add_argument("--base_url", default="http://127.0.0.1:8000")
    parser.add_argument("--api_key_env", default="OPENAI_API_KEY")
    parser.add_argument("--scripted_responses", default="")
