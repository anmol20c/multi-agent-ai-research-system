from agents import llm

print("Testing Groq AI...")

try:
    response = llm.invoke("Say hello in one sentence.")
    print("\nModel response:")
    print(response.content)

except Exception as e:
    print("\nError occurred:")
    print(e)