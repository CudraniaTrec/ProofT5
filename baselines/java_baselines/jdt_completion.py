from __future__ import annotations

import json
import os
import select
import subprocess
import threading
import time
from pathlib import Path
from typing import Any


JAVA_KEYWORDS = {
    "abstract", "assert", "boolean", "break", "byte", "case", "catch",
    "char", "class", "const", "continue", "default", "do", "double",
    "else", "enum", "extends", "final", "finally", "float", "for",
    "goto", "if", "implements", "import", "instanceof", "int",
    "interface", "long", "native", "new", "null", "package", "private",
    "protected", "public", "return", "short", "static", "strictfp",
    "super", "switch", "synchronized", "this", "throw", "throws",
    "transient", "try", "void", "volatile", "while",
}


def char_may_trigger_completion(char: str) -> bool:
    return char.isalnum() or char in "._$"


def trivially_feasible(token: str) -> bool:
    return bool(token) and (
        not char_may_trigger_completion(token[-1]) or token.strip() in JAVA_KEYWORDS
    )


def completion_continuations(result: Any) -> list[str] | None:
    """Normalize Repilot's modified-JDT source/target completion response."""
    if result is None:
        return None
    if isinstance(result, dict) and "items" in result:
        result = result["items"]
    if not isinstance(result, list):
        return []
    continuations = []
    # ``newCompletion`` returns a replacement range (``source``) and the
    # replacement text (``target``).  Repilot's token-level decoder can only
    # append text; it cannot apply an edit that rewrites characters already
    # emitted by the LM.  Treat such an item as *unknown* instead of silently
    # dropping it and turning a non-empty completion list into an empty one.
    # The latter is an unsound false-prune and was particularly damaging for
    # partially typed Java identifiers and constructor snippets.
    has_non_append_edit = False
    for item in result:
        if not isinstance(item, dict):
            continue
        source = item.get("source")
        target = item.get("target")
        if isinstance(source, str) and isinstance(target, str):
            if target.startswith(source):
                continuations.append(target[len(source) :])
            else:
                has_non_append_edit = True
    if has_non_append_edit:
        return None
    return continuations


def completion_accepts(result: Any) -> bool:
    continuations = completion_continuations(result)
    return continuations is None or bool(continuations)


def cursor_position(text: str) -> dict[str, int]:
    lines = text.split("\n")
    return {"line": len(lines) - 1, "character": len(lines[-1])}


def discover_jdt_command(
    repo_root: Path,
    java: str = "java",
    *,
    join_completion: bool = False,
    completion_timeout_ms: int | None = None,
) -> list[str]:
    """Return the modified Eclipse JDT-LS command used by Repilot.

    The default command is kept byte-for-byte compatible with the frozen
    upstream-faithful run.  ``join_completion`` waits for the IDE lifecycle
    jobs before asking for proposals, and ``completion_timeout_ms`` gives the
    modified completion handler enough time to finish semantic analysis.  Both
    are JDT/Repilot settings; this function deliberately has no SynCode or
    grammar-mask dependency.
    """
    product = (
        repo_root
        / "third_party"
        / "baselines"
        / "eclipse.jdt.ls"
        / "org.eclipse.jdt.ls.product"
        / "target"
        / "repository"
    )
    launchers = sorted((product / "plugins").glob("org.eclipse.equinox.launcher_*.jar"))
    config = product / "config_linux"
    if not launchers or not config.is_dir():
        raise FileNotFoundError(
            "modified JDT LS is not built; run baselines/java_baselines/build_jdtls.sh"
        )
    command = [java]
    if join_completion:
        # JDTLanguageServer exposes this exact property value (the Java
        # constant is named JAVA_LSP_JOIN_ON_COMPLETION).  Waiting avoids
        # querying a stale completion index while the incremental compiler is
        # still processing the preceding didChange notification.
        command.append("-Djava.lsp.joinOnCompletion=true")
    if completion_timeout_ms is not None:
        if completion_timeout_ms <= 0:
            raise ValueError("completion_timeout_ms must be positive")
        command.append(f"-Dcompletion.timeout={int(completion_timeout_ms)}")
    command.extend([
        "-Declipse.application=org.eclipse.jdt.ls.core.id1",
        "-Dosgi.bundles.defaultStartLevel=4",
        "-Declipse.product=org.eclipse.jdt.ls.core.product",
        "-Dlog.level=ERROR",
        "-noverify",
        "-Xmx1G",
        "--add-modules=ALL-SYSTEM",
        "--add-opens", "java.base/java.util=ALL-UNNAMED",
        "--add-opens", "java.base/java.lang=ALL-UNNAMED",
        "-jar", str(launchers[-1]),
        "-configuration", str(config),
    ])
    return command


class RepilotJdtClient:
    """Small adapter of Repilot's `newCompletion` JDT protocol."""

    def __init__(
        self,
        command: list[str],
        workspace: Path,
        java_home: Path,
        timeout: float = 60.0,
    ) -> None:
        self.workspace = workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.data_dir = self.workspace / ".jdt-data"
        self.data_dir.mkdir(exist_ok=True)
        self.timeout = timeout
        self.process = subprocess.Popen(
            command + ["-data", str(self.data_dir)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("failed to open JDT language-server pipes")
        self.stdin = self.process.stdin
        self.stdout = self.process.stdout
        self._write_lock = threading.Lock()
        self._next_id = 1
        self._version = 0
        # Repilot's ``pruned-mem`` mode memoizes feasibility decisions for a
        # generated prefix.  The standalone adapter uses the complete trial
        # source as the key, which is safe for this one-file benchmark and
        # avoids asking the IDE for the same proposal list repeatedly across
        # candidate ranks.
        self._completion_cache: dict[str, list[str] | None] = {}
        self.completion_cache_hits = 0
        self.completion_cache_misses = 0
        self.uri = (self.workspace / "Main.java").as_uri()
        self.document = ""
        self._document_open = False
        self.request(
            "initialize",
            {
                "processId": self.process.pid,
                "rootPath": str(self.workspace),
                "rootUri": self.workspace.as_uri(),
                "capabilities": {
                    "textDocument": {
                        "synchronization": {"dynamicRegistration": True},
                        "completion": {
                            "dynamicRegistration": True,
                            "contextSupport": True,
                            "completionItem": {
                                "snippetSupport": True,
                                "commitCharactersSupport": True,
                                "documentationFormat": ["markdown", "plaintext"],
                                "deprecatedSupport": True,
                                "preselectSupport": True,
                                "insertReplaceSupport": True,
                                "resolveSupport": {
                                    "properties": [
                                        "documentation",
                                        "detail",
                                        "additionalTextEdits",
                                    ]
                                },
                            },
                        },
                    }
                },
                "initializationOptions": {
                    "bundles": [],
                    "workspaceFolders": [self.workspace.as_uri()],
                    "settings": {
                        "java": {
                            "home": str(java_home),
                            "autobuild": {"enabled": True},
                            "completion": {
                                "enabled": True,
                                "maxResults": 0,
                                "guessMethodArguments": False,
                                "favoriteStaticMembers": [
                                    "org.junit.Assert.*",
                                    "org.junit.Assume.*",
                                    "org.junit.jupiter.api.Assertions.*",
                                    "org.junit.jupiter.api.Assumptions.*",
                                ],
                                "filteredTypes": [
                                    "java.awt.*",
                                    "com.sun.*",
                                    "sun.*",
                                    "jdk.*",
                                ],
                                "importOrder": ["java", "javax", "org", "com"],
                            },
                            "errors": {"incompleteClasspath": {"severity": "warning"}},
                        }
                    },
                },
                "workspaceFolders": [
                    {"uri": self.workspace.as_uri(), "name": self.workspace.name}
                ],
            },
        )
        self.notify("initialized", {})

    def _send(self, message: dict[str, Any]) -> None:
        body = json.dumps(message).encode()
        framed = f"Content-Length: {len(body)}\r\n\r\n".encode() + body
        with self._write_lock:
            self.stdin.write(framed)
            self.stdin.flush()

    def _receive(self, timeout: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            ready, _, _ = select.select([self.stdout], [], [], max(0.0, deadline - time.monotonic()))
            if not ready:
                break
            line = self.stdout.readline()
            if not line:
                stderr = b""
                if self.process.stderr is not None:
                    stderr = self.process.stderr.read()
                raise RuntimeError(
                    "JDT language server exited: " + stderr.decode(errors="replace")[-2000:]
                )
            if not line.lower().startswith(b"content-length:"):
                continue
            length = int(line.split(b":", 1)[1].strip())
            while True:
                separator = self.stdout.readline()
                if separator in {b"\r\n", b"\n", b""}:
                    break
            return json.loads(self.stdout.read(length))
        raise TimeoutError("timed out waiting for JDT language server")

    def request(self, method: str, params: dict[str, Any]) -> Any:
        request_id = self._next_id
        self._next_id += 1
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + self.timeout
        while True:
            message = self._receive(max(0.1, deadline - time.monotonic()))
            if "method" in message and "id" in message:
                self._send({"jsonrpc": "2.0", "id": message["id"], "result": None})
                continue
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise RuntimeError(f"JDT {method} failed: {message['error']}")
            return message.get("result")

    def notify(self, method: str, params: dict[str, Any]) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def open_document(self, source: str) -> None:
        if self._document_open:
            self.update_document(source)
            return
        self.document = source
        (self.workspace / "Main.java").write_text(source)
        self.notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": self.uri,
                    "languageId": "java",
                    "version": self._version,
                    "text": source,
                }
            },
        )
        self._version += 1
        self._document_open = True

    def update_document(self, source: str) -> None:
        self.document = source
        self.notify(
            "textDocument/didChange",
            {
                "textDocument": {"uri": self.uri, "version": self._version},
                "contentChanges": [{"text": source}],
            },
        )
        self._version += 1

    def token_feasible(self, prefix: str, token: str) -> tuple[bool, list[str] | None]:
        trial = prefix + token
        self.update_document(trial)
        if trial in self._completion_cache:
            self.completion_cache_hits += 1
            continuations = self._completion_cache[trial]
            return continuations is None or bool(continuations), continuations
        self.completion_cache_misses += 1
        result = self.request(
            "newCompletion",
            {
                "textDocument": {"uri": self.uri},
                "position": cursor_position(trial),
            },
        )
        continuations = completion_continuations(result)
        self._completion_cache[trial] = continuations
        return continuations is None or bool(continuations), continuations

    def close(self) -> None:
        if self.process.poll() is not None:
            return
        try:
            self.request("shutdown", {})
            self.notify("exit", {})
            self.process.wait(timeout=15)
        except Exception:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def __enter__(self) -> "RepilotJdtClient":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
