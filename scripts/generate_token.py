import sys
import os
sys.path.append(os.getcwd())

from ai_architect.utils.license import LicenseManager

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/generate_token.py <USER_ID> [DAYS]")
        return
    
    user_id = sys.argv[1]
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    
    token = LicenseManager.generate_token(user_id, days)
    print(f"\n--- ARCHAI PILOT LICENSE TOKEN ---")
    print(f"User: {user_id}")
    print(f"Validity: {days} days")
    print(f"Token:\n{token}\n")
    print(f"Command: ai-architect --license {token}")

if __name__ == "__main__":
    main()
