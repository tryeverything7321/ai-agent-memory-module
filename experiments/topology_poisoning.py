from __future__ import annotations


def inject_phrase_into_context(
    context: str,
    phrase: str,
    repetitions: int,
) -> str:
    if repetitions <= 0:
        return context
    lines = context.splitlines()
    injected = []
    remaining = repetitions
    for line in lines:
        if line.strip() and remaining > 0:
            injected.append(f"{phrase}: {line}")
            remaining -= 1
        else:
            injected.append(line)
    while remaining > 0:
        injected.append(f"{phrase}: synthetic reminder {remaining}")
        remaining -= 1
    return "\n".join(injected)
