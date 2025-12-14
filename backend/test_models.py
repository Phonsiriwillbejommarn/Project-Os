import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
print(f"Checking models with API Key: {api_key[:5]}...{api_key[-5:] if api_key else 'None'}")

if not api_key:
    print("Error: GEMINI_API_KEY not found.")
    exit(1)

try:
    client = genai.Client(api_key=api_key)
    print("Client initialized. Listing models...")
    
    # Try to list models. The method might vary slightly depending on SDK version, 
    # but client.models.list() is standard for the new SDK.
    for m in client.models.list():
        print(f"Model: {m.name}")
        # print(dir(m)) # Uncomment to debug attributes if needed
            
except Exception as e:
    print(f"Error listing models: {e}")
