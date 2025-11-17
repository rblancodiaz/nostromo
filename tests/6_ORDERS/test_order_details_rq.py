"""
Tests for OrderDetailsRQ tool.
"""

import pytest
from unittest.mock import AsyncMock, patch
from tools.ctorders.order_details_rq import OrderDetailsRQHandler, call_order_details_rq
from config import ValidationError, AuthenticationError, APIError


class TestOrderDetailsRQ:
    """Test suite for OrderDetailsRQ tool."""
    
    @pytest.fixture
    def handler(self):
        """Create a handler instance for testing."""
        return OrderDetailsRQHandler()
    
    @pytest.fixture
    def sample_order_ids(self):
        """Sample order IDs for testing."""
        return ["ORD123456", "ORD789012"]
    
    @pytest.fixture
    def sample_origin_ids(self):
        """Sample origin order IDs for testing."""
        return ["BK123456", "BK789012"]
    
    @pytest.fixture
    def mock_auth_response(self):
        """Mock authentication response."""
        return {
            "Token": "test_token_12345",
            "Response": {
                "StatusCode": 200,
                "RequestId": "REQ123",
                "Timestamp": "2024-01-15T10:30:00Z",
                "TimeResponse": 150
            }
        }
    
    @pytest.fixture
    def mock_order_details_response(self):
        """Mock order details response."""
        return {
            "OrderDetails": [
                {
                    "OrderId": "ORD123456",
                    "OrderIdOrigin": "BK123456",
                    "BasketId": "BSK789",
                    "OrderRPH": 1,
                    "Origin": "booking.com",
                    "OriginAds": "google_ads",
                    "OriginContext": "mobile_app",
                    "OrderLanguage": "es",
                    "OrderStatusDetail": {
                        "OrderState": "confirm",
                        "PaymentState": "partial",
                        "PaymentMethod": "card",
                        "NoShow": False,
                        "PaymentType": "deposit",
                        "WhenPay": "now",
                        "CreationDate": "2024-01-15T09:00:00Z",
                        "LastUpdate": "2024-01-15T09:30:00Z"
                    },
                    "OrderAmountsDetail": {
                        "Currency": "EUR",
                        "AmountFinal": 250.00,
                        "AmountTotal": 275.00,
                        "AmountBase": 200.00,
                        "AmountTaxes": 50.00,
                        "AmountTouristTax": 25.00
                    },
                    "CustomerDetail": {
                        "Title": "Mr",
                        "Firstname": "John",
                        "Surname": "Doe",
                        "Address": "123 Main St",
                        "Zip": "28001",
                        "City": "Madrid",
                        "Country": "es",
                        "Phone": "+34666777888",
                        "Email": "john.doe@example.com",
                        "Passaport": "12345678A"
                    },
                    "HotelRoomSummaryDetail": [
                        {
                            "HotelRoomAvailabilityId": "AVAIL123",
                            "ArrivalDate": "2024-02-01",
                            "DepartureDate": "2024-02-05",
                            "HotelRoomRPH": 1,
                            "HotelReferenceRPH": {
                                "ReferenceRPHType": "HotelRoomRPH",
                                "ReferenceRPHValue": 1
                            },
                            "HotelRoomBasicDetail": {
                                "HotelId": "H123",
                                "HotelHash": "hash123",
                                "HotelName": "Test Hotel",
                                "HotelRoomId": "R456",
                                "HotelRoomName": "Deluxe Room",
                                "HotelRoomDescription": "Spacious deluxe room",
                                "HotelRoomArea": 25.5,
                                "Hidden": False,
                                "Order": 1,
                                "UpgradeClass": 1,
                                "UpgradeAllowed": "always"
                            },
                            "AmountsDetail": {
                                "Currency": "EUR",
                                "AmountFinal": 200.00,
                                "AmountTotal": 200.00,
                                "AmountBase": 200.00,
                                "AmountTaxes": 0.00,
                                "AmountTouristTax": 0.00
                            }
                        }
                    ],
                    "HotelGuestSummaryDetail": [
                        {
                            "HotelGuestRPH": 1,
                            "HotelReferenceRPH": {
                                "ReferenceRPHType": "HotelRoomRPH",
                                "ReferenceRPHValue": 1
                            },
                            "HotelGuestDetail": {
                                "Type": "ad",
                                "Age": 35,
                                "Firstname": "John",
                                "Surname": "Doe",
                                "Email": "john.doe@example.com"
                            }
                        }
                    ],
                    "HotelBoardSummaryDetail": [
                        {
                            "HotelBoardRPH": 1,
                            "HotelReferenceRPH": {
                                "ReferenceRPHType": "HotelRoomRPH",
                                "ReferenceRPHValue": 1
                            },
                            "HotelBoardDetail": {
                                "HotelId": "H123",
                                "HotelBoardId": "BB",
                                "HotelBoardType": {
                                    "Code": "breakfast",
                                    "Name": "Breakfast"
                                },
                                "HotelBoardName": "Bed & Breakfast",
                                "HotelBoardDescription": "Room with breakfast included"
                            }
                        }
                    ],
                    "HotelRateSummaryDetail": [],
                    "HotelOfferSummaryDetail": [],
                    "HotelExtraSummaryDetail": [],
                    "PackageSummaryDetail": [],
                    "GenericProductSummaryDetail": [],
                    "OrderPaymentDetail": [
                        {
                            "Id": "PAY123",
                            "Method": "card",
                            "CreationDate": "2024-01-15T09:00:00Z",
                            "Description": "Credit card payment",
                            "Removed": False,
                            "AmountDetail": {
                                "Currency": "EUR",
                                "AmountFinal": 50.00,
                                "AmountTotal": 50.00,
                                "AmountBase": 50.00,
                                "AmountTaxes": 0.00,
                                "AmountTouristTax": 0.00
                            }
                        }
                    ],
                    "OrderCreditCardDetail": [
                        {
                            "Number": "**** **** **** 1234",
                            "Type": "visa"
                        }
                    ],
                    "OrderPaymentToken": [],
                    "OrderCancelPenaltyDetail": [],
                    "Hash": [
                        {
                            "Hash": "abc123hash",
                            "HashType": "mybooking"
                        }
                    ],
                    "OrderScheduledPaymentDetail": [],
                    "OrderTracking": {
                        "Approved": True,
                        "Confirmed": True
                    },
                    "AdvertisingAuthorization": True,
                    "WithDataAuthorization": True,
                    "LoyaltyAuthorization": False,
                    "ExternalSystem": [],
                    "Domain": "test.neobookings.com"
                }
            ],
            "Response": {
                "StatusCode": 200,
                "RequestId": "REQ456",
                "Timestamp": "2024-01-15T10:30:05Z",
                "TimeResponse": 200
            }
        }
    
    @pytest.mark.asyncio
    async def test_execute_success_single_order_by_id(self, handler, mock_auth_response, mock_order_details_response):
        """Test successful retrieval of single order details by order ID."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_order_details_response]
            
            arguments = {
                "order_ids": ["ORD123456"],
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert len(result["data"]["order_details"]) == 1
            
            order = result["data"]["order_details"][0]
            assert order["order_id"] == "ORD123456"
            assert order["order_id_origin"] == "BK123456"
            assert order["basket_id"] == "BSK789"
            assert order["origin"] == "booking.com"
            assert order["order_language"] == "es"
            assert order["order_status"]["order_state"] == "confirm"
            assert order["order_status"]["payment_state"] == "partial"
            assert order["customer"]["firstname"] == "John"
            assert order["customer"]["surname"] == "Doe"
            assert order["customer"]["email"] == "john.doe@example.com"
            assert len(order["room_summaries"]) == 1
            assert len(order["guest_summaries"]) == 1
            assert len(order["board_summaries"]) == 1
            
            assert "Retrieved details for 1 order(s)" in result["message"]
            
            # Verify API calls
            assert mock_client.post.call_count == 2
            assert mock_client.set_token.called
    
    @pytest.mark.asyncio
    async def test_execute_success_by_origin_ids(self, handler, sample_origin_ids, mock_auth_response, mock_order_details_response):
        """Test successful retrieval of order details by origin IDs."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = [mock_auth_response, mock_order_details_response]
            
            arguments = {
                "order_ids_origin": sample_origin_ids,
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert result["data"]["search_criteria"]["order_ids_origin"] == sample_origin_ids
            assert result["data"]["search_criteria"]["order_ids"] == []
            assert "Retrieved details for 1 order(s)" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_no_orders_found(self, handler, mock_auth_response):
        """Test when no order details are found."""
        with patch('config.NeobookingsHTTPClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            empty_response = {
                "OrderDetails": [],
                "Response": {
                    "StatusCode": 200,
                    "RequestId": "REQ456",
                    "Timestamp": "2024-01-15T10:30:05Z",
                    "TimeResponse": 200
                }
            }
            mock_client.post.side_effect = [mock_auth_response, empty_response]
            
            arguments = {
                "order_ids": ["ORD999999"],
                "language": "es"
            }
            
            result = await handler.execute(arguments)
            
            assert result["success"] is True
            assert len(result["data"]["order_details"]) == 0
            assert "No order details found" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_no_identifiers(self, handler):
        """Test validation error when no order identifiers are provided."""
        arguments = {
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "At least one order identifier is required" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_both_identifiers(self, handler):
        """Test validation error when both order IDs and origin IDs are provided."""
        arguments = {
            "order_ids": ["ORD123456"],
            "order_ids_origin": ["BK123456"],
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "Cannot provide both order_ids and order_ids_origin" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_empty_order_ids(self, handler):
        """Test validation error for empty order IDs list."""
        arguments = {
            "order_ids": [],
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "At least one order ID is required" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_validation_error_invalid_order_id(self, handler):
        """Test validation error for invalid order ID format."""
        arguments = {
            "order_ids": ["", "  ", "VALID123"],
            "language": "es"
        }
        
        result = await handler.execute(arguments)
        
        assert result["success"] is False
        assert "must be a non-empty string" in result["message"]
    
    @pytest.mark.asyncio
    async def test_call_order_details_success(self, sample_order_ids):
        """Test the MCP tool handler for successful order details retrieval."""
        with patch('tools.ctorders.order_details_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "search_criteria": {
                        "order_ids": sample_order_ids,
                        "order_ids_origin": []
                    },
                    "order_details": [
                        {
                            "order_id": "ORD123456",
                            "order_id_origin": "BK123456",
                            "basket_id": "BSK789",
                            "order_rph": 1,
                            "origin": "booking.com",
                            "origin_ads": "google_ads",
                            "order_language": "es",
                            "order_status": {
                                "order_state": "confirm",
                                "payment_state": "partial",
                                "payment_method": "card",
                                "no_show": False,
                                "payment_type": "deposit",
                                "when_pay": "now",
                                "creation_date": "2024-01-15T09:00:00Z",
                                "last_update": "2024-01-15T09:30:00Z"
                            },
                            "amounts": {
                                "currency": "EUR",
                                "amount_final": 250.00,
                                "amount_total": 275.00,
                                "amount_base": 200.00,
                                "amount_taxes": 50.00,
                                "amount_tourist_tax": 25.00
                            },
                            "customer": {
                                "title": "Mr",
                                "firstname": "John",
                                "surname": "Doe",
                                "email": "john.doe@example.com",
                                "phone": "+34666777888",
                                "address": "123 Main St",
                                "city": "Madrid",
                                "country": "es",
                                "zip": "28001"
                            },
                            "room_summaries": [
                                {
                                    "availability_id": "AVAIL123",
                                    "arrival_date": "2024-02-01",
                                    "departure_date": "2024-02-05",
                                    "hotel_id": "H123",
                                    "hotel_name": "Test Hotel",
                                    "room_id": "R456",
                                    "room_name": "Deluxe Room",
                                    "room_description": "Spacious deluxe room"
                                }
                            ],
                            "guest_summaries": [
                                {
                                    "type": "ad",
                                    "age": 35,
                                    "firstname": "John",
                                    "surname": "Doe",
                                    "email": "john.doe@example.com"
                                }
                            ],
                            "board_summaries": [
                                {
                                    "board_id": "BB",
                                    "board_name": "Bed & Breakfast",
                                    "board_type": "breakfast"
                                }
                            ],
                            "payment_details": [
                                {
                                    "id": "PAY123",
                                    "method": "card",
                                    "amount": 50.00,
                                    "currency": "EUR",
                                    "description": "Credit card payment"
                                }
                            ],
                            "credit_cards": [
                                {
                                    "masked_number": "**** **** **** 1234",
                                    "type": "visa"
                                }
                            ],
                            "tracking": {
                                "approved": True,
                                "confirmed": True
                            },
                            "authorizations": {
                                "advertising": True,
                                "with_data": True,
                                "loyalty": False
                            }
                        }
                    ],
                    "summary": {
                        "total_requested": 1,
                        "total_found": 1,
                        "success_rate": 100.0
                    },
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 200}
                },
                "message": "Retrieved details for 1 order(s)"
            }
            
            arguments = {"order_ids": ["ORD123456"]}
            result = await call_order_details_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Details Retrieved" in response_text
            assert "Orders Found: 1" in response_text
            assert "Success Rate: 100.0%" in response_text
            assert "ORD123456" in response_text
            assert "BK123456" in response_text
            assert "booking.com" in response_text
            assert "Status: confirm" in response_text
            assert "Payment: partial" in response_text
            assert "John Doe" in response_text
            assert "john.doe@example.com" in response_text
            assert "Test Hotel" in response_text
            assert "Deluxe Room" in response_text
    
    @pytest.mark.asyncio
    async def test_call_order_details_no_orders(self):
        """Test the MCP tool handler when no orders are found."""
        with patch('tools.ctorders.order_details_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": True,
                "data": {
                    "search_criteria": {
                        "order_ids": ["ORD999999"],
                        "order_ids_origin": []
                    },
                    "order_details": [],
                    "summary": {
                        "total_requested": 1,
                        "total_found": 0,
                        "success_rate": 0.0
                    },
                    "request_metadata": {
                        "RequestId": "REQ123",
                        "Timestamp": "2024-01-15T10:30:00Z"
                    },
                    "api_response": {"TimeResponse": 200}
                },
                "message": "No order details found for the requested identifiers"
            }
            
            arguments = {"order_ids": ["ORD999999"]}
            result = await call_order_details_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Details Retrieved" in response_text
            assert "Orders Found: 0" in response_text
            assert "Success Rate: 0.0%" in response_text
            assert "No order details found" in response_text
    
    @pytest.mark.asyncio
    async def test_call_order_details_failure(self):
        """Test the MCP tool handler for failed order details retrieval."""
        with patch('tools.ctorders.order_details_rq.handler') as mock_handler:
            mock_handler.execute.return_value = {
                "success": False,
                "message": "Invalid order identifiers provided",
                "error": {"code": "400", "details": "Order not found"}
            }
            
            arguments = {"order_ids": ["INVALID123"]}
            result = await call_order_details_rq(arguments)
            
            assert len(result) == 1
            response_text = result[0].text
            assert "Order Details Retrieval Failed" in response_text
            assert "Invalid order identifiers provided" in response_text
            assert "Troubleshooting" in response_text
