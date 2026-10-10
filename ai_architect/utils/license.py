import hmac
import hashlib
import json
import base64
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict

class LicenseManager:
    """Handles secure, signed license tokens for ArchAI Pilot."""
    
    SECRET_KEY = b"archai-pilot-secure-key-2026" # In production, this would be an environment variable or KMS key

    @staticmethod
    def generate_token(user_id: str, days: int = 7) -> str:
        """Generates a signed HMAC token valid for N days."""
        start_ts = int(time.time())
        expiry_ts = start_ts + (days * 24 * 60 * 60)
        
        payload = {
            "u": user_id,
            "s": start_ts,
            "e": expiry_ts
        }
        
        payload_json = json.dumps(payload, separators=(',', ':'))
        payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip("=")
        
        signature = hmac.new(
            LicenseManager.SECRET_KEY,
            payload_b64.encode(),
            hashlib.sha256
        ).digest()
        
        sig_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")
        return f"{payload_b64}.{sig_b64}"

    @staticmethod
    def validate_token(token: str) -> Dict:
        """Validates token signature and expiry. Returns payload if valid, raises error otherwise."""
        try:
            parts = token.split(".")
            if len(parts) != 2:
                raise ValueError("Invalid token format.")
            
            payload_b64, sig_b64 = parts
            
            # Verify Signature
            expected_sig = hmac.new(
                LicenseManager.SECRET_KEY,
                payload_b64.encode(),
                hashlib.sha256
            ).digest()
            
            # Re-pad b64 if needed
            pad_needed = 4 - (len(sig_b64) % 4)
            actual_sig = base64.urlsafe_b64decode(sig_b64 + ("=" * (pad_needed % 4)))
            
            if not hmac.compare_digest(expected_sig, actual_sig):
                raise ValueError("Token signature mismatch. Tampering detected.")
            
            # Decode Payload
            pad_needed_p = 4 - (len(payload_b64) % 4)
            payload_json = base64.urlsafe_b64decode(payload_b64 + ("=" * (pad_needed_p % 4))).decode()
            payload = json.loads(payload_json)
            
            # Check Expiry
            now = int(time.time())
            if now > payload["e"]:
                raise ValueError(f"License expired on {LicenseManager.expiry_text(payload['e'])}")
            
            return payload
            
        except Exception as e:
            raise ValueError(f"License Validation Failed: {str(e)}")

    @staticmethod
    def expiry_text(expiry_ts) -> str:
        """UTC expiry date. datetime.fromtimestamp raises OSError on Windows for
        dates past year 3000, so long-lived tokens must not go through it."""
        try:
            moment = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=int(expiry_ts))
            return moment.strftime('%Y-%m-%d')
        except (OverflowError, ValueError, TypeError):
            return "never (beyond year 9999)"

    @staticmethod
    def inspect_token(token: Optional[str]) -> Dict:
        """Non-raising status: state is VALID, EXPIRED, INVALID or MISSING."""
        if not token:
            return {"state": "MISSING", "user": None, "expires": None, "days_left": None,
                    "reason": "No license token supplied (ARCHAI_LICENSE or --license)."}
        try:
            payload = LicenseManager.validate_token(token)
        except ValueError as e:
            state = "EXPIRED" if "expired on" in str(e) else "INVALID"
            return {"state": state, "user": None, "expires": None, "days_left": None, "reason": str(e)}
        return {"state": "VALID", "user": payload.get("u"),
                "expires": LicenseManager.expiry_text(payload["e"]),
                "days_left": max(0, (int(payload["e"]) - int(time.time())) // 86400), "reason": None}

    @staticmethod
    def get_token_info(token: str) -> str:
        """Returns a human-readable string of token status."""
        info = LicenseManager.inspect_token(token)
        if info["state"] == "VALID":
            return f"Valid pilot license for {info['user']} (Expires: {info['expires']})"
        return f"{info['state']}: {info['reason']}"
