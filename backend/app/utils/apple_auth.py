"""Apple Sign In authentication utilities"""

import jwt
import requests
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import HTTPException, status


# Apple's public keys URL
APPLE_PUBLIC_KEYS_URL = "https://appleid.apple.com/auth/keys"


def get_apple_public_keys() -> Dict[str, Any]:
    """
    Fetch Apple's public keys for JWT verification.

    Returns:
        Dictionary of Apple's public keys

    Raises:
        HTTPException: If fetching keys fails
    """
    try:
        response = requests.get(APPLE_PUBLIC_KEYS_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch Apple public keys: {str(e)}"
        )


def verify_apple_identity_token(identity_token: str) -> Dict[str, Any]:
    """
    Verify Apple identity token (JWT) and extract claims.

    Apple identity tokens are JWTs signed with Apple's private key.
    We verify the signature using Apple's public keys.

    Args:
        identity_token: The identity token from Apple Sign In

    Returns:
        Dictionary containing verified token claims:
        - sub: Apple user ID (unique identifier)
        - email: User's email (may be privatized)
        - email_verified: Whether email is verified
        - iss: Issuer (should be "https://appleid.apple.com")
        - aud: Audience (your app's bundle ID)
        - iat: Issued at timestamp
        - exp: Expiration timestamp

    Raises:
        HTTPException: If token verification fails
    """
    try:
        # Decode token header to get key ID
        unverified_header = jwt.get_unverified_header(identity_token)
        key_id = unverified_header.get("kid")

        if not key_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid identity token: missing key ID"
            )

        # Fetch Apple's public keys
        apple_keys = get_apple_public_keys()

        # Find the matching public key
        public_key = None
        for key in apple_keys.get("keys", []):
            if key.get("kid") == key_id:
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                break

        if not public_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid identity token: public key not found"
            )

        # Verify and decode the token
        # Note: We're not validating 'aud' (audience) here to keep it flexible
        # In production, you should validate audience matches your app's bundle ID
        decoded_token = jwt.decode(
            identity_token,
            public_key,
            algorithms=["RS256"],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_iss": True,
                "require": ["sub", "iss", "iat", "exp"]
            },
            issuer="https://appleid.apple.com"
        )

        # Validate required claims
        if not decoded_token.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid identity token: missing subject (Apple user ID)"
            )

        return decoded_token

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identity token has expired"
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid identity token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token verification failed: {str(e)}"
        )


def extract_apple_user_info(identity_token: str, full_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract user information from Apple identity token.

    Args:
        identity_token: The verified identity token
        full_name: Optional full name from Apple authorization

    Returns:
        Dictionary with user info:
        - apple_id: Apple's unique user identifier
        - email: User's email (may be privatized like abc@privaterelay.appleid.com)
        - email_verified: Whether email is verified by Apple
        - full_name: User's full name (if provided)
    """
    # Verify token and get claims
    claims = verify_apple_identity_token(identity_token)

    return {
        "apple_id": claims["sub"],
        "email": claims.get("email", ""),
        "email_verified": claims.get("email_verified", False),
        "full_name": full_name
    }
