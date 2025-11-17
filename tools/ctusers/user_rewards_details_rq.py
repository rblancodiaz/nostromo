"""
UserRewardsDetailsRQ - User Rewards Details Tool

This tool retrieves detailed information about users subscribed to rewards programs in the Neobookings system.
"""

import json
from typing import Dict, Any, List, Optional
from mcp.types import Tool
from mcp.types import TextContent, ImageContent, EmbeddedResource
import structlog

from config import (
    NeobookingsConfig, 
    NeobookingsHTTPClient,
    create_standard_request,
    format_response,
    ValidationError,
    AuthenticationError,
    APIError,
    logger,
    sanitize_string
)

# Tool definition
USER_REWARDS_DETAILS_RQ_TOOL = Tool(
    name="user_rewards_details_rq",
    description="""
    Retrieve detailed information about users subscribed to rewards programs.
    
    This tool allows querying detailed information about users who are subscribed
    to loyalty/rewards programs in the Neobookings system. It provides comprehensive
    user profile data including personal information, contact details, and 
    subscription history.
    
    Parameters:
    - user_reward_ids (required): List of user reward IDs (email addresses) to query
    - language (optional): Language code for the request
    
    Returns:
    - Detailed user profile information
    - Contact information and preferences
    - Subscription and creation dates
    - Personal identification details
    - Address and location information
    
    Example usage:
    "Get rewards details for user john@example.com"
    "Retrieve loyalty program information for customers"
    "Check user subscription status and profile data"
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "user_reward_ids": {
                "type": "array",
                "description": "List of user reward IDs (email addresses) to query",
                "items": {
                    "type": "string",
                    "format": "email",
                    "description": "User email address registered in rewards program"
                },
                "minItems": 1,
                "maxItems": 100
            },
            "language": {
                "type": "string",
                "description": "Language code for the request",
                "enum": ["es", "en", "fr", "de", "it", "pt"],
                "default": "es"
            }
        },
        "required": ["user_reward_ids"],
        "additionalProperties": False
    }
)


class UserRewardsDetailsRQHandler:
    """Handler for the UserRewardsDetailsRQ endpoint."""
    
    def __init__(self):
        self.config = NeobookingsConfig.from_env()
        self.logger = logger.bind(tool="user_rewards_details_rq")
    
    def _validate_user_reward_ids(self, user_ids: List[str]) -> List[str]:
        """Validate and sanitize user reward IDs (email addresses)."""
        if not user_ids:
            raise ValidationError("User reward IDs are required")
        
        if len(user_ids) > 100:
            raise ValidationError("Maximum 100 user reward IDs allowed")
        
        validated_ids = []
        for i, user_id in enumerate(user_ids):
            if not isinstance(user_id, str) or not user_id.strip():
                raise ValidationError(f"User ID {i+1}: must be a non-empty string")
            
            sanitized_id = sanitize_string(user_id.strip())
            if not sanitized_id:
                raise ValidationError(f"User ID {i+1}: invalid format after sanitization")
            
            # Basic email validation
            if "@" not in sanitized_id or "." not in sanitized_id:
                raise ValidationError(f"User ID {i+1}: must be a valid email address")
            
            validated_ids.append(sanitized_id)
        
        return validated_ids
    
    def _format_user_rewards_details(self, users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format user rewards details for readable output."""
        formatted_users = []
        
        for user in users:
            formatted_user = {
                "contact_information": {
                    "email": user.get("Email"),
                    "phone": user.get("Phone"),
                    "mobile": user.get("Mobile"),
                    "fax": user.get("Fax")
                },
                "personal_information": {
                    "title": user.get("Title"),
                    "first_name": user.get("Firstname"),
                    "last_name": user.get("Surname"),
                    "passport": user.get("Passport"),
                    "date_of_birth": user.get("DateOfBirthday")
                },
                "address_information": {
                    "address": user.get("Address"),
                    "postal_code": user.get("Zip"),
                    "city": user.get("City"),
                    "country": user.get("Country")
                },
                "subscription_information": {
                    "date_created": user.get("DateCreated"),
                    "last_update": user.get("LastUpdate")
                }
            }
            
            formatted_users.append(formatted_user)
        
        return formatted_users
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the user rewards details request.
        
        Args:
            arguments: Tool arguments containing user reward IDs
            
        Returns:
            Dictionary containing the user rewards details
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If authentication fails
            APIError: If the API call fails
        """
        try:
            # Extract and validate arguments
            user_reward_ids = arguments.get("user_reward_ids", [])
            language = arguments.get("language", "es")
            
            # Validate inputs
            validated_user_ids = self._validate_user_reward_ids(user_reward_ids)
            
            self.logger.info(
                "Retrieving user rewards details",
                user_count=len(validated_user_ids),
                language=language
            )
            
            # Create request payload
            request_data = create_standard_request(language)
            request_payload = {
                "Request": request_data["Request"],
                "UserRewardId": validated_user_ids
            }
            
            # Make API call with authentication
            async with NeobookingsHTTPClient(self.config) as client:
                # First authenticate
                auth_request = {
                    "Request": request_data["Request"],
                    "Credentials": {
                        "ClientCode": self.config.client_code,
                        "SystemCode": self.config.system_code,
                        "Username": self.config.username,
                        "Password": self.config.password
                    }
                }
                auth_response = await client.post("/AuthenticatorRQ", auth_request, require_auth=False)
                token = auth_response.get("Token")
                if not token:
                    raise AuthenticationError("Failed to obtain authentication token")
                
                client.set_token(token)
                
                # Make the user rewards details request
                response = await client.post("/UserRewardsDetailsRQ", request_payload)
            
            # Extract data from response
            user_rewards_details = response.get("UserRewardsDetails", [])
            api_response = response.get("Response", {})
            
            # Format results
            formatted_users = self._format_user_rewards_details(user_rewards_details)
            
            # Log successful operation
            self.logger.info(
                "User rewards details retrieved successfully",
                users_found=len(formatted_users),
                request_id=request_data["Request"]["RequestId"]
            )
            
            # Prepare response data
            response_data = {
                "search_criteria": {
                    "user_reward_ids": validated_user_ids,
                    "language": language
                },
                "users": formatted_users,
                "summary": {
                    "total_users_found": len(formatted_users),
                    "users_requested": len(validated_user_ids)
                },
                "request_metadata": request_data["Request"],
                "api_response": api_response
            }
            
            return format_response(
                response_data,
                success=True,
                message=f"Found details for {len(formatted_users)} users"
            )
            
        except ValidationError as e:
            self.logger.error("Validation error", error=str(e))
            return format_response(
                {"error_code": e.error_code, "details": e.details},
                success=False,
                message=f"Validation error: {e.message}"
            )
            
        except AuthenticationError as e:
            self.logger.error("Authentication error", error=str(e))
            return format_response(
                {"error_code": e.error_code, "details": e.details},
                success=False,
                message=f"Authentication failed: {e.message}"
            )
            
        except APIError as e:
            self.logger.error("API error", error=str(e))
            return format_response(
                {"error_code": e.error_code, "details": e.details},
                success=False,
                message=f"API error: {e.message}"
            )
            
        except Exception as e:
            self.logger.error("Unexpected error", error=str(e))
            return format_response(
                {"error_type": type(e).__name__},
                success=False,
                message=f"Unexpected error: {str(e)}"
            )


# Global handler instance
handler = UserRewardsDetailsRQHandler()


async def call_user_rewards_details_rq(arguments: Dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
    """MCP tool handler for the UserRewardsDetailsRQ endpoint.
    
    Args:
        arguments: Arguments passed to the tool
        
    Returns:
        List containing the response as TextContent
    """
    try:
        result = await handler.execute(arguments)
        
        # Format the result as a readable text response
        if result["success"]:
            data = result["data"]
            users = data["users"]
            summary = data["summary"]
            search_criteria = data["search_criteria"]
            
            response_text = f"""👥 **User Rewards Details Results**

📊 **Search Summary:**
- **Users Requested**: {summary['users_requested']}
- **Users Found**: {summary['total_users_found']}
- **Language**: {search_criteria['language'].upper()}

"""
            
            if users:
                response_text += f"""👤 **User Details ({len(users)}):**
{'='*80}
"""
                
                for i, user in enumerate(users, 1):
                    contact = user.get('contact_information', {})
                    personal = user.get('personal_information', {})
                    address = user.get('address_information', {})
                    subscription = user.get('subscription_information', {})
                    
                    response_text += f"""
👤 **User #{i}**
{'-'*60}

📧 **Contact Information:**
- **Email**: {contact.get('email', 'N/A')}
- **Phone**: {contact.get('phone', 'N/A')}
- **Mobile**: {contact.get('mobile', 'N/A')}
- **Fax**: {contact.get('fax', 'N/A')}

👨‍💼 **Personal Information:**
- **Title**: {personal.get('title', 'N/A')}
- **Name**: {personal.get('first_name', 'N/A')} {personal.get('last_name', 'N/A')}
- **Date of Birth**: {personal.get('date_of_birth', 'N/A')}
- **Passport/ID**: {personal.get('passport', 'N/A')}

🏠 **Address Information:**
- **Address**: {address.get('address', 'N/A')}
- **City**: {address.get('city', 'N/A')}
- **Postal Code**: {address.get('postal_code', 'N/A')}
- **Country**: {address.get('country', 'N/A')}

📅 **Subscription Information:**
- **Date Created**: {subscription.get('date_created', 'N/A')}
- **Last Update**: {subscription.get('last_update', 'N/A')}

"""
            else:
                response_text += f"""❌ **No Users Found**

None of the requested user reward IDs were found in the system.

**Requested IDs:**
{chr(10).join(f'• {user_id}' for user_id in search_criteria['user_reward_ids'])}

🔍 **Possible Reasons:**
- User IDs are not subscribed to rewards programs
- Email addresses may not be registered in the system
- Users may have unsubscribed from rewards programs
- Email addresses may contain typos
"""
            
            response_text += f"""

🏷️ **Request Details:**
- **Request ID**: {data['request_metadata']['RequestId']}
- **Timestamp**: {data['request_metadata']['Timestamp']}
- **Response Time**: {data.get('api_response', {}).get('TimeResponse', 'N/A')}ms

💡 **Usage Tips:**
- Use valid email addresses for user reward IDs
- Ensure users are subscribed to rewards programs
- Check email address format and spelling
- Use this data for customer service and account management
- Personal information is sensitive - handle with care
"""
                
        else:
            response_text = f"""❌ **User Rewards Details Retrieval Failed**

**Error**: {result['message']}

**Details**: {json.dumps(result.get('error', {}), indent=2)}

🔧 **Troubleshooting:**
- Verify the user reward IDs are valid email addresses
- Check that users are subscribed to rewards programs
- Ensure authentication credentials are correct
- Verify API access permissions
- Check for typos in email addresses
- Contact support if the issue persists

🔒 **Privacy Note:**
User rewards details contain sensitive personal information.
Ensure proper data handling and privacy compliance.
"""
        
        return [TextContent(type="text", text=response_text)]
        
    except Exception as e:
        error_text = f"""💥 **Tool Execution Error**

An unexpected error occurred while retrieving user rewards details:

**Error**: {str(e)}
**Type**: {type(e).__name__}

Please check the tool configuration and try again.
"""
        return [TextContent(type="text", text=error_text)]
