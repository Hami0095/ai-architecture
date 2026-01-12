#!/bin/bash

# ArchAI Distribution Orchestrator
# This script prepares the pilot package, generates a test token, and zips the bundle.

echo "🛑 Starting ArchAI Pilot Distribution Sequence..."

# 1. Generate a Test Token for the 'Pilot-Demo' user
echo "🎫 Generating 7-day pilot token..."
TOKEN=$(python scripts/generate_token.py Pilot-Demo 7 | tail -n 1 | awk '{print $NF}')

# 2. Run the build script
echo "📦 Building self-contained binaries..."
python scripts/build_pilot_bundle.py

# 3. Inject the demo token into the distribution guide for easy onboarding
echo "📝 Customizing Pilot Guide with demo token..."
echo "" >> dist_pilot/PILOT_GUIDE.md
echo "### YOUR PILOT TOKEN" >> dist_pilot/PILOT_GUIDE.md
echo "Run this to activate your session:" >> dist_pilot/PILOT_GUIDE.md
echo "./ai-architect --license $TOKEN" >> dist_pilot/PILOT_GUIDE.md

# 4. Final Zipping (platform specific extension added in build script)
echo "🤐 Finalizing distribution zip..."
# (The build script already handles basic zipping, but we ensure the latest guide is in there)
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    powershell "Compress-Archive -Path dist_pilot/* -DestinationPath archai_pilot_dist.zip -Force"
else
    zip -r archai_pilot_dist.zip dist_pilot/
fi

echo "✅ Distribution bundle ready: archai_pilot_dist.zip"
echo "🚀 Phir-Milty-Hain!"
