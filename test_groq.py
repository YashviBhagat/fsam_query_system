import os
from dotenv import load_dotenv
from groq import Groq

# Load your API key from .env
load_dotenv()

# Connect to Groq
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Send a simple test message
response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "user", "content": "Say exactly: Groq connection successful!"}
    ]
)

print(response.choices[0].message.content)