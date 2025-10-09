# dhwani_frappe_base/api/jwt_auth.py

import frappe
from cryptography.fernet import Fernet
import ast
import time
from datetime import datetime, timedelta

def get_secret():
    """Fetch encryption secret from site config or generate a fallback."""
    return frappe.conf.get("encryption_key") or frappe.generate_hash(length=32)

def encode_api_credentials(api_key, api_secret, expires_in=86400):
    """
    Encrypt API credentials using Fernet encryption.
    token
    Args:
        api_key (str): The API key
        api_secret (str): The API secret
        expires_in (int): Token expiraget_secrettion time in seconds (default: 24 hours)
    
    Returns:
        str: Encrypted token
    """
    try:
        cipher_suite = Fernet(get_secret())
        
        # Calculate expiration timestamp
        expires_at = int(time.time()) + expires_in
        
        # Encrypt the payload
        payload = {
            "api_key": api_key,
            "api_secret": api_secret,
            "expires_at": expires_at
        }
        encrypted_payload = cipher_suite.encrypt(str(payload).encode())
        return encrypted_payload.decode()
    except Exception as e:
        raise frappe.AuthenticationError("Failed to encode API credentials")

def decode_api_credentials(encrypted_token):
    """
    Decrypt API credentials and check expiration.
    Returns (api_key, api_secret) if valid, else raises AuthenticationError.
    """
    try:
        # Decrypt payload
        cipher_suite = Fernet(get_secret())
        decrypted_payload = cipher_suite.decrypt(encrypted_token.encode())
        payload = ast.literal_eval(decrypted_payload.decode())
        
        # Check if token has expired
        current_time = int(time.time())
        expires_at = payload.get("expires_at")
        
        if not expires_at:
            logger.error("Token missing expiration timestamp")
            raise frappe.AuthenticationError("Invalid token format")
            
        if current_time > expires_at:
            logger.error(f"Token expired at {datetime.fromtimestamp(expires_at)}")
            raise frappe.AuthenticationError("Token has expired")
        
        api_key = payload.get("api_key")
        api_secret = payload.get("api_secret")
        
        if not api_key or not api_secret:
            raise frappe.AuthenticationError("Invalid token payload")
            
        return api_key, api_secret
        
    except Exception as e:
        raise frappe.AuthenticationError("Invalid authentication token")



def token_auth_middleware():
    """
    Middleware to convert encrypted token to Frappe's default auth format.
    """
    try:
        auth_header = frappe.get_request_header("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return  # No token, let Frappe handle as usual

        encrypted_token = auth_header.split(" ", 1)[1].strip()
        api_key, api_secret = decode_api_credentials(encrypted_token)
        
        # Create new headers dict since EnvironHeaders is immutable
        new_headers = dict(frappe.request.headers)
        new_headers["Authorization"] = f"token {api_key}:{api_secret}"
        frappe.request.headers = new_headers
    except frappe.AuthenticationError as e:
        frappe.clear_messages()
        frappe.throw(str(e), frappe.AuthenticationError)
    except Exception as e:
        frappe.throw("Authentication failed", frappe.AuthenticationError)
