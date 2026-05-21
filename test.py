import os
from dotenv import load_dotenv

# 1. Look for the hidden .env file in this folder and load it into memory
load_dotenv()

# 2. Ask the operating system for the key we just loaded
my_key = os.getenv("API_KEY")

# 3. Print it out to prove the python file successfully grabbed it
print(f"Success! Python sees the key: {my_key}")