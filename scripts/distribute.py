import subprocess
import os
import shutil
import sys
from ai_architect.utils.license import LicenseManager

def distribute():
    print("🛑 Starting ArchAI Pilot Distribution Sequence...")

    # 1. Generate a Test Token
    user_id = os.environ.get("PILOT_USER_ID", "Pilot-Demo")
    days = int(os.environ.get("PILOT_DAYS", 7))
    
    print(f"🎫 Generating {days}-day pilot token for {user_id}...")
    token = LicenseManager.generate_token(user_id, days)
    print(f"Token: {token}")

    # 2. Run the build script
    print("📦 Building self-contained binaries for current platform...")
    # We execute the script as a subprocess to keep environments clean
    subprocess.run([sys.executable, "scripts/build_pilot_bundle.py"], check=True)

    # 3. Inject the demo token into the distribution guide
    print("📝 Customizing Pilot Guide with demo token...")
    guide_path = "dist_pilot/PILOT_GUIDE.md"
    if os.path.exists(guide_path):
        with open(guide_path, "a") as f:
            f.write(f"\n### YOUR PILOT TOKEN\n")
            f.write(f"Run this to activate your session:\n")
            f.write(f"ai-architect --license {token}\n")

    # 4. Final Zipping
    print("🤐 Finalizing distribution zip...")
    zip_name = f"archai_pilot_{sys.platform}_dist"
    shutil.make_archive(zip_name, 'zip', "dist_pilot")

    print(f"\n✅ Distribution bundle ready: {zip_name}.zip")
    print("🚀 Note: For macOS, run this same script on a Mac host.")
    print("PHIR-MILTY-HAIN!")

if __name__ == "__main__":
    distribute()
