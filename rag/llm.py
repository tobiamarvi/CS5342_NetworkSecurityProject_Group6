"""Local LLM via Ollama. The client talks only to localhost:11434, so no course text leaves the machine."""
import ollama

# The plain qwen3:4b tag is the thinking build: it leaks reasoning text and is slow on a 4 GB GPU.
MODEL = "qwen3:4b-instruct"


def chat(system, user, temperature=0.2):
    reply = ollama.chat(
        model=MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        # Ollama's default 4096-token window would cut off 5 x 500-word sources
        options={"temperature": temperature, "num_ctx": 8192},
    )
    return reply.message.content.strip()
