import subprocess
import os
import shutil
import sys

def build_binary():
    """Builds a self-contained ArchAI binary for the current platform."""
    print("🚀 ArchAI Pilot: Initiating High-Integrity Build...")
    
    # 1. Platform Detection
    is_windows = sys.platform.startswith('win')
    ext = ".exe" if is_windows else ""
    binary_name = f"ai-architect{ext}"
    
    # 2. Preparation
    dist_dir = "dist_pilot"
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    os.makedirs(dist_dir)

    # 3. PyInstaller Orchestration
    # --onefile: Bundle everything into a single binary
    # --hidden-import: Ensure dynamic imports (like PM connectors) are included
    try:
        print("📦 Bundling dependencies (this may take a few minutes)...")
        cmd = [
            "pyinstaller",
            "--onefile",
            "--name", "ai-architect",
            "--paths", ".",
            "--add-data", f"archai_config.yaml{';' if is_windows else ':'}.",
            "--hidden-import", "cryptography",
            "--hidden-import", "pydantic",
            "--hidden-import", "shlex",
            "archai.py"
        ]
        subprocess.run(cmd, check=True)
        
        # 4. Final Assembly
        print("📂 Finalizing pilot package...")
        generated_bin = os.path.join("dist", binary_name)
        target_bin = os.path.join(dist_dir, binary_name)
        shutil.move(generated_bin, target_bin)
        
        # Build README for Pilot
        readme_content = """# ArchAI Pilot Binary
        
Usage:
1. Apply License: ai-architect --license <TOKEN>
2. Run Audit: ai-architect AUDIT .
3. Exit: PHIR-MILTY-HAIN
"""
        with open(os.path.join(dist_dir, "PILOT_GUIDE.md"), "w") as f:
            f.write(readme_content)

        print(f"✅ Build Complete: {dist_dir}/{binary_name}")
        print(f"🔒 Next Step: Sign the binary with your private developer certificate.")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Build Failed: {e}")
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    # Ensure we are in the project root
    if not os.path.exists("ai_architect"):
        print("Error: Run this script from the project root.")
    else:
        build_binary()
