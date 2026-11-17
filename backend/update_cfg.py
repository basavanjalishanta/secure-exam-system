with open("c:/Users/Supriya/Desktop/secure-exam-system/backend/config.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if "AI_PROVIDER = _get" in line:
        new_lines.append('    # --- AI provider abstraction ---\n')
        new_lines.append('    # AI_PROVIDER = "groq" | "grok" | "ollama" | "mock"\n')
        new_lines.append('    AI_PROVIDER = _get("AI_PROVIDER", "groq").lower()\n\n')
        new_lines.append('    # Cloud LLM (Groq / Grok / OpenAI-compatible endpoint)\n')
        new_lines.append('    GROQ_API_KEY = _get("GROQ_API_KEY", "")\n')
        new_lines.append('    GROK_API_KEY = _get("GROK_API_KEY", "")\n')
        new_lines.append('    CLOUD_API_KEY = _get("CLOUD_API_KEY", "") or GROQ_API_KEY or GROK_API_KEY\n\n')
        new_lines.append('    GROQ_BASE_URL = _get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")\n')
        new_lines.append('    GROK_BASE_URL = _get("GROK_BASE_URL", "https://api.x.ai/v1")\n')
        new_lines.append('    CLOUD_BASE_URL = _get("CLOUD_BASE_URL", "") or (GROK_BASE_URL if "grok" in AI_PROVIDER else GROQ_BASE_URL)\n\n')
        new_lines.append('    GROQ_MODEL = _get("GROQ_MODEL", "llama-3.1-8b-instant")\n')
        new_lines.append('    GROK_MODEL = _get("GROK_MODEL", "grok-beta")\n')
        new_lines.append('    CLOUD_MODEL = _get("CLOUD_MODEL", "") or (GROK_MODEL if "grok" in AI_PROVIDER else GROQ_MODEL)\n')
        new_lines.append('    CLOUD_TIMEOUT = int(_get("CLOUD_TIMEOUT", "60"))\n\n')
        new_lines.append('    # Local Ollama\n')
        new_lines.append('    LLAMA_BASE_URL = _get("LLAMA_BASE_URL", "http://localhost:11434/v1")\n')
        new_lines.append('    LLAMA_API_KEY = _get("LLAMA_API_KEY", "not-needed-for-local")\n')
        new_lines.append('    LLAMA_MODEL = _get("LLAMA_MODEL", "llama3.2:1b")\n')
        new_lines.append('    LLAMA_TIMEOUT = int(_get("LLAMA_TIMEOUT", "180"))\n')
        new_lines.append('    LLAMA_TEMPERATURE = float(_get("LLAMA_TEMPERATURE", "0.2"))\n')
        new_lines.append('    LLM_CONCURRENCY = int(_get("LLM_CONCURRENCY", "1"))\n')
        skip = True
    elif "EMBEDDING_PROVIDER =" in line:
        skip = False
        new_lines.append(line)
    elif not skip:
        new_lines.append(line)

with open("c:/Users/Supriya/Desktop/secure-exam-system/backend/config.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Updated config.py successfully")
