import os
from google import genai
from dotenv import load_dotenv

load_dotenv("backend/.env")
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("No API key found")
    exit(1)

client = genai.Client(api_key=api_key)
try:
    models = client.models.list()
    found = False
    print("Available models:")
    for m in models:
        print(f"- {m.name}")
        if "gemini-3-flash" in m.name:
            found = True
            
    if found:
        print("\nSUCCESS: gemini-3-flash found!")
    else:
        print("\nFAILURE: gemini-3-flash NOT found.")
except Exception as e:
    print(f"Error listing models: {e}")
