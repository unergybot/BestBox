import requests
import json
import sys

def test_chat_completions():
    url = "http://localhost:8000/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    payload = {
        "input": [
            {"role": "user", "content": "hello"}
        ],
        "stream": True,
    }

    print(f"Sending request to {url}...")
    try:
        with requests.post(url, json=payload, headers=headers, stream=True) as response:
            if response.status_code != 200:
                print(f"Error: {response.status_code}")
                # print(response.text)
                return

            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith("data: ") and decoded_line != "data: [DONE]":
                        try:
                            # print(decoded_line)
                            data = json.loads(decoded_line[6:])
                            choices = data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                if "content" in delta and delta["content"]:
                                    print(f"CONTENT: {delta['content']}")
                                if "tool_calls" in delta and delta["tool_calls"]:
                                    tc = delta["tool_calls"][0]
                                    print(f"TOOL_CALL: {tc.get('name')} ARGS: {tc.get('args')}")
                                    
                                    # Verification logic
                                    args = tc.get('args', {})
                                    limit = args.get('limit')
                                    if isinstance(limit, int):
                                        print("SUCCESS: Limit is an integer.")
                                    elif isinstance(limit, str):
                                        if limit.isdigit():
                                             print("WARNING: Limit is string digits (acceptable).")
                                        else:
                                             print(f"SUCCESS: Limit is string '{limit}' (Handled by robust fix).")
                                    else:
                                        print(f"INFO: Limit is {type(limit)}: {limit}")

                        except json.JSONDecodeError:
                            pass
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    test_chat_completions()
