from __future__ import annotations

from .common import JavaTask


SYSTEM = (
    "You generate Java source code. Return only one complete Java source file, "
    "without Markdown fences or explanation."
)


def initial_messages(task: JavaTask) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": (
                "Complete the following Java programming task. Preserve the requested "
                "class and method signature and return the complete source file.\n\n"
                + task.prompt
            ),
        },
    ]

def repair_messages(
    task: JavaTask,
    previous_source: str,
    diagnostics: str,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": (
                "Repair the Java source below using only the compiler diagnostics. "
                "Preserve the task, class, and method signature. Return the complete "
                "source file. No tests or test results are available.\n\n"
                "TASK PREFIX:\n"
                f"{task.prompt}\n\nCURRENT SOURCE:\n{previous_source}\n\n"
                f"JAVAC DIAGNOSTICS:\n{diagnostics}"
            ),
        },
    ]
