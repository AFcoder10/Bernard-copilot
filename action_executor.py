import json
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
        data = json.loads(json_payload)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON payload -> {e}")
        return {"error": "Invalid JSON"}

    action_name = data.get("action")
    if not action_name:
        print("Error: No 'action' key found in JSON.")
        return {"error": "No action specified"}

    # Extract arguments — supports dict, list, or no args
    kwargs = data.get("args", {})
    
    # If the LLM forgot to wrap args in an "args" key, try to recover
    if not kwargs and len(data) > 1:
        kwargs = {k: v for k, v in data.items() if k != "action"}

    if action_name not in TOOL_REGISTRY:
        print(f"Error: Unknown action '{action_name}'")
        return {"error": f"Unknown action: {action_name}"}

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
