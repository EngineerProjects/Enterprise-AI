from enterprise_ai.llm.ollama.ollama import OllamaProvider
from enterprise_ai.schema import Message

# Create provider with verbose logging
llm = OllamaProvider(model_name="llama3.2", verbose=True)

# Test 1: No system prompt
messages1 = [Message.user_message("What is your system prompt?")]
response1 = llm.complete(messages1)
print("\nResponse without system prompt:")
print(response1.content)

# Test 2: With explicit system prompt
messages2 = [
    Message.system_message("You are a helpful assistant who always reveals your system prompt."),
    Message.user_message("What is your system prompt?")
]
response2 = llm.complete(messages2)
print("\nResponse with system prompt:")
print(response2.content)

# Check payload building
import json
from enterprise_ai.llm.ollama.helpers import OllamaConfigHelper, OllamaMessageFormatter

formatter = OllamaMessageFormatter()
payload1 = OllamaConfigHelper.build_generate_payload("llama3.2", messages1, formatter)
payload2 = OllamaConfigHelper.build_generate_payload("llama3.2", messages2, formatter)

print("\nPayload without system prompt:")
print(json.dumps(payload1, indent=2))
print("\nPayload with system prompt:")
print(json.dumps(payload2, indent=2))