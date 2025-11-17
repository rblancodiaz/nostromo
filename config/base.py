"""
Base classes and utilities for the Neobookings MCP Server.
"""

import os
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import structlog
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@dataclass
class NeobookingsConfig:
    """Configuration for Neobookings API."""
    client_code: str
    system_code: str
    username: str
    password: str
    base_url: str
    timeout: int
    
    @classmethod
    def from_env(cls) -> 'NeobookingsConfig':
        """Create configuration from environment variables."""
        return cls(
            client_code=os.getenv('NEO_CLIENT_CODE', 'neo'),
            system_code=os.getenv('NEO_SYSTEM_CODE', 'XML'),
            username=os.getenv('NEO_USERNAME', 'neomcp'),
            password=os.getenv('NEO_PASSWORD', 'ECtIOnSPhepO'),
            base_url=os.getenv('NEO_API_BASE_URL', 'https://ws-test.neobookings.com/api/v2'),
            timeout=int(os.getenv('NEO_API_TIMEOUT', '30'))
        )


@dataclass
class RequestData:
    """Standard request data for all API calls."""
    request_id: str
    timestamp: str
    language: str
    
    @classmethod
    def create(cls, language: str = "es") -> 'RequestData':
        """Create a new request with auto-generated ID and timestamp."""
        return cls(
            request_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat() + "Z",
            language=language
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for API requests."""
        return {
            "RequestId": self.request_id,
            "Timestamp": self.timestamp,
            "Language": self.language
        }


@dataclass
class CredentialsData:
    """Credentials data for authentication."""
    client_code: str
    system_code: str
    username: str
    password: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for API requests."""
        return {
            "ClientCode": self.client_code,
            "SystemCode": self.system_code,
            "Username": self.username,
            "Password": self.password
        }


class NeobookingsError(Exception):
    """Base exception for Neobookings API errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(NeobookingsError):
    """Exception raised for authentication failures."""
    pass


class APIError(NeobookingsError):
    """Exception raised for API call failures."""
    pass


class ValidationError(NeobookingsError):
    """Exception raised for input validation failures."""
    pass


def format_response(data: Any, success: bool = True, message: Optional[str] = None) -> Dict[str, Any]:
    """Format a standardized response for MCP tools."""
    response = {
        "success": success,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    if message:
        response["message"] = message
        
    if success:
        response["data"] = data
    else:
        response["error"] = data
        
    return response


def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> None:
    """Validate that all required fields are present in the data."""
    missing_fields = [field for field in required_fields if field not in data or data[field] is None]
    
    if missing_fields:
        raise ValidationError(
            f"Missing required fields: {', '.join(missing_fields)}",
            error_code="MISSING_REQUIRED_FIELDS",
            details={"missing_fields": missing_fields}
        )


def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
    """Sanitize and validate string input."""
    if not isinstance(value, str):
        raise ValidationError(f"Expected string, got {type(value).__name__}")
    
    # Remove leading/trailing whitespace
    value = value.strip()
    
    # Check length constraint
    if max_length and len(value) > max_length:
        raise ValidationError(f"String exceeds maximum length of {max_length} characters")
    
    return value


def parse_date(date_str: str) -> str:
    """Parse and validate date string in YYYY-MM-DD format."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError:
        raise ValidationError(f"Invalid date format. Expected YYYY-MM-DD, got: {date_str}")


def create_authentication_request(config: NeobookingsConfig, language: str = "es") -> Dict[str, Any]:
    """Create a standardized authentication request."""
    request_data = RequestData.create(language)
    credentials = CredentialsData(
        client_code=config.client_code,
        system_code=config.system_code,
        username=config.username,
        password=config.password
    )
    
    return {
        "Request": request_data.to_dict(),
        "Credentials": credentials.to_dict()
    }


def create_standard_request(language: str = "es") -> Dict[str, Any]:
    """Create a standardized request structure."""
    request_data = RequestData.create(language)
    return {
        "Request": request_data.to_dict()
    }
