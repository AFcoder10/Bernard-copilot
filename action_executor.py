import json
import re
from tools import TOOL_REGISTRY

def execute_action(json_payload: str):
    """
    Parses a JSON payload from the LLM and executes the corresponding tool.
    This is a generic executor — it doesn't care what the tool is.
    Expected format: {"action": "tool_name", "args": {"key": "value"}} or {"action": "tool_name", "args": ["a", "b"]}
    """
    print(f"\n--- Action Executor ---")
    print(f"Received Payload: {json_payload}")
    
    try:
        # Strip markdown code fences if the LLM wrapped it
        cleaned = json_payload.strip()
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        
        # Robustly extract the first complete JSON object
        brace_depth = 0
        start = cleaned.find('{')
        if start == -1:
            return {"error": "No JSON object found in payload"}
        
        for i in range(start, len(cleaned)):
            if cleaned[i] == '{':
                brace_depth += 1
            elif cleaned[i] == '}':
                brace_depth -= 1
                if brace_depth == 0:
                    cleaned = cleaned[start:i+1]
                    break
            
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON payload -> {e}")
        return {"error": f"Invalid JSON: {e}"}

    # Handle OpenAI-style tool_calls wrapper if the LLM hallucinates it
    if "tool_calls" in data and isinstance(data["tool_calls"], list) and len(data["tool_calls"]) > 0:
        call = data["tool_calls"][0]
        if "function" in call:
            func = call["function"]
            if isinstance(func, dict):
                data["action"] = func.get("name")
                data["args"] = func.get("arguments", {})
            elif isinstance(func, str):
                data["action"] = func
                data["args"] = call.get("args", call.get("arguments", {}))

    action_name = data.get("action")
    if not action_name:
        print("Error: No 'action' key found in JSON.")
        return {"error": "No action specified"}

    # Extract arguments — supports dict, list, or no args
    kwargs = data.get("args", {})
    
    # If the LLM forgot to wrap args in an "args" key, try to recover
    if "args" not in data and len(data) > 1:
        kwargs = {k: v for k, v in data.items() if k != "action"}

    if action_name not in TOOL_REGISTRY:
        # Fuzzy match: try to find the closest tool name
        close_matches = [name for name in TOOL_REGISTRY if action_name.lower() in name.lower() or name.lower() in action_name.lower()]
        if close_matches:
            action_name = close_matches[0]
            print(f"Fuzzy-matched to: {action_name}")
        else:
            print(f"Error: Unknown action '{action_name}'")
            return {"error": f"Unknown action: {action_name}. Available tools: {', '.join(list(TOOL_REGISTRY.keys())[:10])}..."}

    tool_func = TOOL_REGISTRY[action_name]
    
    print(f"Executing: {action_name} with args: {kwargs}")
    try:
        if isinstance(kwargs, dict):
            result = tool_func(**kwargs)
        elif isinstance(kwargs, list):
            result = tool_func(*kwargs)
        else:
            result = tool_func()
             
        print(f"Result: {result}")
        print("-----------------------")
        return result
    except TypeError as e:
        # Common issue: LLM passes wrong argument names. Show what was expected.
        import inspect
        sig = inspect.signature(tool_func)
        print(f"Execution Error: {e}")
        print(f"Expected signature: {action_name}{sig}")
        print("-----------------------")
        return {"error": f"{e}. Expected: {action_name}{sig}"}
    except Exception as e:
        print(f"Execution Error: {e}")
        print("-----------------------")
        return {"error": str(e)}

if __name__ == "__main__":
    print("Running Tests...")
    
    # Test: Run a command
    payload1 = '{"action": "run_command", "args": {"command": "echo hello from Bernard"}}'
    execute_action(payload1)
    
    # Test: Type text
    payload2 = '{"action": "type_text", "args": {"text": "Hello from Bernard!"}}'
    execute_action(payload2)
