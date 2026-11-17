import os
import time
from dotenv import load_dotenv
load_dotenv("c:/Users/Supriya/Desktop/secure-exam-system/backend/.env")
from openai import OpenAI

api_key = os.getenv("GROQ_API_KEY")
print("Testing Groq with key:", api_key[:12] + "...")

client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)
t0 = time.time()
res = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[
        {"role": "system", "content": "You are an exam setter. Output JSON only."},
        {"role": "user", "content": "Generate 1 question on Data Structures. Return JSON: {\"question\": \"text\"}"}
    ],
    response_format={"type": "json_object"},
    max_tokens=150
)
t1 = time.time()
print(f"Groq Response time: {t1-t0:.2f}s!")
print(res.choices[0].message.content)
