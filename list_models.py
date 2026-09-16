import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
models = client.models.list()
print(json.dumps([m.id for m in models.data], indent=2))
