"""
Test configuration and fixtures.
"""

import pytest
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure test environment variables
os.environ.setdefault('NEO_CLIENT_CODE', 'neo')
os.environ.setdefault('NEO_SYSTEM_CODE', 'XML')
os.environ.setdefault('NEO_USERNAME', 'neomcp')
os.environ.setdefault('NEO_PASSWORD', 'ECtIOnSPhepO')
os.environ.setdefault('NEO_API_BASE_URL', 'https://ws-test.neobookings.com/api/v2')
os.environ.setdefault('NEO_API_TIMEOUT', '30')


@pytest.fixture(scope="session")
def test_config():
    """Provide test configuration."""
    return {
        'client_code': 'neo',
        'system_code': 'XML',
        'username': 'neomcp',
        'password': 'ECtIOnSPhepO',
        'base_url': 'https://ws-test.neobookings.com/api/v2',
        'timeout': 30
    }


@pytest.fixture
def sample_auth_response():
    """Provide a sample authentication response."""
    return {
        "Token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.example",
        "Response": {
            "StatusCode": 200,
            "RequestId": "12345678-1234-1234-1234-123456789012",
            "Timestamp": "2024-01-15T10:30:00Z",
            "TimeResponse": 150,
            "Success": {},
            "Warning": [],
            "Error": []
        }
    }


@pytest.fixture
def sample_error_response():
    """Provide a sample error response."""
    return {
        "Response": {
            "StatusCode": 401,
            "RequestId": "12345678-1234-1234-1234-123456789012",
            "Timestamp": "2024-01-15T10:30:00Z",
            "TimeResponse": 100,
            "Error": [
                {
                    "Code": "INVALID_CREDENTIALS",
                    "Description": "The provided credentials are invalid"
                }
            ]
        }
    }
