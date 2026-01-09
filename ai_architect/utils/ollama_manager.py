import subprocess
import shutil
import sys
import time

def run_command(command):
    """Runs a shell command and returns formatted output and exit code."""
    try:
        result = subprocess.run(
            command, 
            capture_output=True, 
            text=True, 
            shell=True
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        return "", str(e), -1

def is_ollama_installed():
    """Checks if Ollama executable is found in path."""
    return shutil.which("ollama") is not None

def get_available_models():
    """Returns a list of installed models."""
    stdout, _, code = run_command("ollama list")
    if code != 0:
        return []
    
    # Parse output: NAME ID SIZE MODIFIED
    # Skip header
    lines = stdout.split('\n')[1:]
    models = []
    for line in lines:
        parts = line.split()
        if parts:
            models.append(parts[0])
    return models

def check_ollama_status():
    """
    Checks connection to Ollama.
    Returns: 'running', 'stopped', 'not_installed'
    """
    if not is_ollama_installed():
        return 'not_installed'
    
    # Try a simple list command to check if daemon is responsive
    _, stderr, code = run_command("ollama list")
    
    # If connection refused or socket error, it usually goes to stderr or nonzero code
    if "could not connect" in stderr.lower() or "connection refused" in stderr.lower():
        return 'stopped'
    
    if code == 0:
        return 'running'
        
    return 'stopped' # Default fall back

def pull_model(model_name):
    """Pulls a model using subprocess (blocking)."""
    print(f"--- Pulling model {model_name}... (This might take a while) ---")
    proc = subprocess.Popen(["ollama", "pull", model_name], stdout=sys.stdout, stderr=sys.stderr)
    proc.wait()
    return proc.returncode == 0

def initialize_ollama(preferred_model="qwen3-coder:480b-cloud"):
    """
    Orchestrates the Ollama setup.
    1. Checks installation.
    2. Checks service status.
    3. Selects or pulls model.
    """
    print("\n[Ollama Manager] Initializing AI Runtime...")
    
    status = check_ollama_status()
    
    if status == 'not_installed':
        print("CRITICAL: Ollama is not installed.")
        print("Please install Ollama from https://ollama.com/ and try again.")
        sys.exit(1)
        
    if status == 'stopped':
        print("WARNING: Ollama service seems to be stopped.")
        print("Attempting to start 'ollama serve' in background...")
        # Note: Starting serve from python script is tricky across OS. 
        # Safest is to ask user.
        print("Please run 'ollama serve' in a separate terminal.")
        # Optional: We could try Popen(['ollama', 'serve']) but it blocks.
        sys.exit(1)

    # Service is running, check models.
    models = get_available_models()
    print(f"[Ollama Manager] Detected models: {models}")
    
    selected_model = None

    # 1. If preferred model is already there
    if preferred_model in models:
        selected_model = preferred_model
    # 2. If preferred model is NOT there, but NO models exist -> Pull
    elif not models:
        print(f"[Ollama Manager] No models found. Pulling default: {preferred_model}")
        success = pull_model(preferred_model)
        if success:
            selected_model = preferred_model
        else:
            print("Failed to pull model. Exiting.")
            sys.exit(1)
    # 3. If models exist but not preferred -> Ask user or fallback
    else:
        # Simple Logic: Check if 'gemma' or 'llama' exists and pick it
        # Otherwise Prompt user
        print(f"[Ollama Manager] Preferred model '{preferred_model}' not found.")
        
        # Try to find a close match
        for m in models:
            if "qwen" in m or "coder" in m or "gemma" in m or "llama" in m:
                print(f"[Ollama Manager] Falling back to available model: {m}")
                return m
                
        # If no obvious match, ask user
        print("Please select a model to use:")
        for i, m in enumerate(models):
            print(f"{i+1}. {m}")
        
        choice = input("Enter number (or 'p' to pull default): ")
        if choice.lower() == 'p':
             pull_model(preferred_model)
             return preferred_model
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                return models[idx]
        except:
            pass
        
        print("Invalid selection. Exiting.")
        sys.exit(1)

    print(f"[Ollama Manager] Selected Model: {selected_model}")
    return selected_model
