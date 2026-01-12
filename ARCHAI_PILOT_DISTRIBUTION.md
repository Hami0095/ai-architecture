# ArchAI Pilot Binary Distribution Plan

## 1. Overview
Secure, signed, and self-contained binary distribution for ArchAI to enable controlled pilot testing without source code exposure.

## 2. Core Security Architecture
| Feature | Implementation | Purpose |
| :--- | :--- | :--- |
| **Packaging** | `PyInstaller` (OneFile) | Self-contained executable with embedded Python runtime. |
| **Code Obfuscation** | `PyArmor` (Pre-bundle) | Prevents reverse engineering of the bundled `.pyc` files. |
| **Integrity** | SHA-256 Graph Core Hash | Verifies the deterministic logic engine hasn't been tampered with. |
| **Licensing** | HMAC-SHA256 Signed Tokens | Enforces 7-day trial periods and user identity. |
| **Signing** | `osslsigncode` / `codesign` | Native OS-level signatures to prevent binary replacement. |

## 3. Implementation Workflow

### Step A: License Token System (Completed)
- Location: `ai_architect/utils/license.py`
- Payload: User ID, Issue TS, Expiry TS.
- Signature: HMCA-SHA256 with project secret.

### Step B: The Enforcement Gate (Completed)
- CLI now checks `ARCHAI_LICENSE` environment variable.
- Gate blocks entry if token is missing/expired.
- New flags: `--license <TOKEN>`, `--check-token`.

### Step C: Multi-Platform Build Script (`scripts/build_pilot_bundle.py`)
This script automates the creation of the distributable `.zip`.

```python
# scripts/build_pilot_bundle.py
import subprocess
import os
import shutil

def build():
    print("🚀 Starting ArchAI Pilot Build...")
    dist_path = "dist_pilot"
    if os.path.exists(dist_path): shutil.rmtree(dist_path)
    
    # 1. Package with PyInstaller (Embeds everything)
    # Using --onefile to ensure no external dependencies
    # Using archai.py as a clean entry point to avoid relative import errors
    cmd = [
        "pyinstaller", 
        "--onefile",
        "--name", "ai-architect",
        "--paths", ".",
        "--add-data", "archai_config.yaml;.",
        "--hidden-import", "cryptography",
        "--hidden-import", "pydantic",
        "--hidden-import", "shlex",
        "archai.py"
    ]
    subprocess.run(cmd, check=True)
    
    # Assembly logic...
```

### Step D: Signing Protocol (Platform Specific)
- **Windows**: `signtool sign /f archai.pfx /p <pass> ai-architect.exe`
- **macOS**: `codesign --force --sign "Developer ID: ArchAI" ai-architect`
- **Linux**: `gpg --clearsign ai-architect`

## 4. Pilot Usage Instructions (README Template)

```markdown
# ArchAI Pilot Tester Guide

Welcome to the ArchAI Pilot! You are testing a deterministic architectural adjudication engine.

## Quick Start
1. Extract the `ai-architect` binary for your platform.
2. Apply your pilot license token:
   `./ai-architect --license <YOUR_TOKEN>`
3. Launch the console:
   `./ai-architect`

## Commands
- `PLAN . "Goal"`: Blueprint your changes.
- `AUDIT .`: Site survey.
- `PHIR-MILTY-HAIN`: Securely exit the session.

## Test Mode
To explore pre-recorded architectural scenarios without analyzing your own code:
`./ai-architect --test-mode`

## Feedback
Report any issues or discrepancies in adjudication:
`./ai-architect --feedback "The risk assessment for X was too conservative"`
```

## 5. Security Recommendations
1. **Rotate the HMAC Key**: Change the `SECRET_KEY` in `license.py` for every major pilot batch.
2. **Environment Stripping**: Ensure the build environment doesn't contain sensitive `.env` files that might be accidentally bundled.
3. **Hardware ID (Optional)**: For high-security pilots, bind tokens to `uuid.getnode()` to prevent token sharing.
