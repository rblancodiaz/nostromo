"""
Tests for HotelSearchRQ tool.
"""

import pytest
from unittest.mock import AsyncMock, patch
from tools.tools_cthotelinventory.hotel_search_rq import HotelSearchRQHandler


class TestHotelSearchRQHandler:
    """Test cases for HotelSearchRQHandler."""
    
    @pytest.fixture
    def handler(self):
        """Create handler instance for testing."""
        return HotelSearchRQHandler()
    
    @pytest.fixture
    def mock_hotel_search_response(self):
        """Mock response for hotel search."""
        return {
            "Response": {
                "StatusCode": 200,
                "RequestId": "test_123",
                "Timestamp": "2024-01-01T00:00:00",
                "TimeResponse": 500
            },
            "CurrentPage": 1,
            "TotalPages": 3,
            "TotalRecords": 75,
            "HotelBasicDetail": [
                {
                    "HotelId": "HTL001",
                    "HotelHash": "hash001",
                    "HotelName": "Grand Palace Hotel",
                    "HotelDescription": "Luxury hotel in city center",
                    "Currency": "EUR",
                    "Rewards": True,
                    "HotelMode": "hotel",
                    "HotelView": "compact",
                    "TimeZone": "Europe/Madrid",
                    "HotelGuestType": [
                        {
                            "GuestType": "ad",
                            "MinAge": 18,
                            "MaxAge": 99
                        }
                    ],
                    "HotelType": [
                        {
                            "Code": "LUX",
                            "Name": "Luxury Hotel"
                        }
                    ],
                    "HotelCategory": [
                        {
                            "Code": "5",
                            "Name": "5 Star"
                        }
                    ],
                    "HotelLocation": {
                        "Address": "Main Street 123",
                        "City": "Madrid",
                        "PostalCode": "28001",
                        "Latitude": 40.4168,
                        "Longitude": -3.7038,
                        "Zone": [
                            {
                                "Code": "MAD",
                                "Name": "Madrid Center"
                            }
                        ],
                        "State": {
                            "Code": "MD",
                            "Name": "Madrid"
                        },
                        "Country": {
                            "Code": "ES",
                            "Name": "Spain"
                        }
                    },
                    "HotelAmenity": [
                        {
                            "Code": "WIFI",
                            "Name": "Free WiFi",
                            "Filterable": True
                        },
                        {
                            "Code": "SPA",
                            "Name": "Spa",
                            "Filterable": True
                        }
                    ],
                    "Media": [
                        {
                            "MediaType": "photo",
                            "Caption": "Hotel Exterior",
                            "Url": "https://example.com/hotel1.jpg",
                            "Main": True,
                            "Order": 1
                        }
                    ]
                },
                {
                    "HotelId": "HTL002",
                    "HotelHash": "hash002",
                    "HotelName": "Budget Inn",
                    "HotelDescription": "Affordable accommodation",
                    "Currency": "EUR",
                    "Rewards": False,
                    "HotelMode": "hotel",
                    "HotelView": "list",
                    "TimeZone": "Europe/Madrid",
                    "HotelLocation": {
                        "Address": "Second Street 456",
                        "City": "Barcelona",
                        "Country": {
                            "Code": "ES",
                            "Name": "Spain"
                        }
                    }
                }
            ]
        }
    
    @pytest.mark.asyncio
    async def test_execute_successful_search(self, handler, mock_hotel_search_response):
        """Test successful hotel search execution."""
        with patch.object(handler.config, 'client_code', 'neo'), \
             patch.object(handler.config, 'system_code', 'XML'), \
             patch.object(handler.config, 'username', 'test'), \
             patch.object(handler.config, 'password', 'test'):
            
            with patch('tools.tools_cthotelinventory.hotel_search_rq.NeobookingsHTTPClient') as mock_client:
                mock_instance = AsyncMock()
                mock_client.return_value.__aenter__.return_value = mock_instance
                
                # Mock authentication response
                mock_instance.post.side_effect = [
                    {"Token": "test_token"},  # Auth response
                    mock_hotel_search_response  # Search response
                ]
                
                arguments = {
                    "hotel_names": ["Palace"],
                    "countries": ["ES"],
                    "zones": ["MAD"],
                    "page": 1,
                    "num_results": 25
                }
                
                result = await handler.execute(arguments)
                
                assert result["success"] is True
                assert len(result["data"]["hotels"]) == 2
                assert result["data"]["summary"]["total_found"] == 75
                assert result["data"]["pagination"]["current_page"] == 1
                assert result["data"]["pagination"]["total_pages"] == 3
                
                # Verify first hotel details
                first_hotel = result["data"]["hotels"][0]
                assert first_hotel["hotel_id"] == "HTL001"
                assert first_hotel["hotel_name"] == "Grand Palace Hotel"
                assert first_hotel["rewards"] is True
                assert first_hotel["location"]["city"] == "Madrid"
                assert len(first_hotel["amenities"]) == 2
    
    @pytest.mark.asyncio
    async def test_execute_with_all_filters(self, handler, mock_hotel_search_response):
        """Test hotel search with all possible filters."""
        with patch.object(handler.config, 'client_code', 'neo'), \
             patch.object(handler.config, 'system_code', 'XML'), \
             patch.object(handler.config, 'username', 'test'), \
             patch.object(handler.config, 'password', 'test'):
            
            with patch('tools.tools_cthotelinventory.hotel_search_rq.NeobookingsHTTPClient') as mock_client:
                mock_instance = AsyncMock()
                mock_client.return_value.__aenter__.return_value = mock_instance
                
                mock_instance.post.side_effect = [
                    {"Token": "test_token"},
                    mock_hotel_search_response
                ]
                
                arguments = {
                    "hotel_names": ["Palace", "Grand"],
                    "countries": ["ES", "FR"],
                    "zones": ["MAD", "BCN"],
                    "hotel_categories": ["4", "5"],
                    "page": 2,
                    "num_results": 50,
                    "language": "en"
                }
                
                result = await handler.execute(arguments)
                
                assert result["success"] is True
                assert result["data"]["search_criteria"]["hotel_names"] == ["Palace", "Grand"]
                assert result["data"]["search_criteria"]["countries"] == ["ES", "FR"]
                assert result["data"]["search_criteria"]["zones"] == ["MAD", "BCN"]
                assert result["data"]["search_criteria"]["categories"] == ["4", "5"]
    
    @pytest.mark.asyncio
    async def test_execute_no_results(self, handler):
        """Test hotel search with no results."""
        empty_response = {
            "Response": {
                "StatusCode": 200,
                "RequestId": "test_123",
                "Timestamp": "2024-01-01T00:00:00",
                "TimeResponse": 250
            },
            "CurrentPage": 1,
            "TotalPages": 0,
            "TotalRecords": 0,
            "HotelBasicDetail": []
        }
        
        with patch.object(handler.config, 'client_code', 'neo'), \
             patch.object(handler.config, 'system_code', 'XML'), \
             patch.object(handler.config, 'username', 'test'), \
             patch.object(handler.config, 'password', 'test'):
            
            with patch('tools.tools_cthotelinventory.hotel_search_rq.NeobookingsHTTPClient') as mock_client:
                mock_instance = AsyncMock()
                mock_client.return_value.__aenter__.return_value = mock_instance
                
                mock_instance.post.side_effect = [
                    {"Token": "test_token"},
                    empty_response
                ]
                
                arguments = {
                    "hotel_names": ["NonexistentHotel"]
                }
                
                result = await handler.execute(arguments)
                
                assert result["success"] is True
                assert len(result["data"]["hotels"]) == 0
                assert result["data"]["summary"]["total_found"] == 0
    
    @pytest.mark.asyncio
    async def test_execute_validation_errors(self, handler):
        """Test various validation error scenarios."""
        # Test invalid page number
        arguments = {"page": 0}
        result = await handler.execute(arguments)
        assert result["success"] is False
        assert "Page number must be at least 1" in result["message"]
        
        # Test invalid num_results
        arguments = {"num_results": 101}
        result = await handler.execute(arguments)
        assert result["success"] is False
        assert "Number of results must be between 1 and 100" in result["message"]
        
        # Test invalid hotel name
        arguments = {"hotel_names": [""]}
        result = await handler.execute(arguments)
        assert result["success"] is False
        assert "Invalid hotel name" in result["message"]
        
        # Test invalid country code
        arguments = {"countries": ["SPAIN"]}  # Should be 2 characters
        result = await handler.execute(arguments)
        assert result["success"] is False
        assert "Country code must be 2 characters" in result["message"]
    
    @pytest.mark.asyncio
    async def test_execute_authentication_failure(self, handler):
        """Test authentication failure handling."""
        with patch.object(handler.config, 'client_code', 'neo'), \
             patch.object(handler.config, 'system_code', 'XML'), \
             patch.object(handler.config, 'username', 'test'), \
             patch.object(handler.config, 'password', 'test'):
            
            with patch('tools.tools_cthotelinventory.hotel_search_rq.NeobookingsHTTPClient') as mock_client:
                mock_instance = AsyncMock()
                mock_client.return_value.__aenter__.return_value = mock_instance
                
                # Mock failed authentication (no token returned)
                mock_instance.post.return_value = {"error": "Invalid credentials"}
                
                arguments = {"countries": ["ES"]}
                result = await handler.execute(arguments)
                
                assert result["success"] is False
                assert "Authentication failed" in result["message"]
    
    @pytest.mark.asyncio
    async def test_pagination_info(self, handler, mock_hotel_search_response):
        """Test pagination information handling."""
        with patch.object(handler.config, 'client_code', 'neo'), \
             patch.object(handler.config, 'system_code', 'XML'), \
             patch.object(handler.config, 'username', 'test'), \
             patch.object(handler.config, 'password', 'test'):
            
            # Test middle page
            mock_hotel_search_response["CurrentPage"] = 2
            mock_hotel_search_response["TotalPages"] = 5
            
            with patch('tools.tools_cthotelinventory.hotel_search_rq.NeobookingsHTTPClient') as mock_client:
                mock_instance = AsyncMock()
                mock_client.return_value.__aenter__.return_value = mock_instance
                
                mock_instance.post.side_effect = [
                    {"Token": "test_token"},
                    mock_hotel_search_response
                ]
                
                arguments = {"page": 2, "num_results": 25}
                result = await handler.execute(arguments)
                
                pagination = result["data"]["pagination"]
                assert pagination["current_page"] == 2
                assert pagination["total_pages"] == 5
                assert pagination["has_next_page"] is True
                assert pagination["has_previous_page"] is True
    
    def test_format_hotel_location(self, handler):
        """Test hotel location formatting."""
        location_data = {
            "Address": "Test Street 123",
            "City": "Madrid",
            "PostalCode": "28001",
            "Latitude": 40.4168,
            "Longitude": -3.7038,
            "Zone": [
                {"Code": "MAD", "Name": "Madrid Center"}
            ],
            "State": {"Code": "MD", "Name": "Madrid"},
            "Country": {"Code": "ES", "Name": "Spain"}
        }
        
        formatted = handler._format_hotel_location(location_data)
        
        assert formatted["address"] == "Test Street 123"
        assert formatted["city"] == "Madrid"
        assert formatted["latitude"] == 40.4168
        assert len(formatted["zones"]) == 1
        assert formatted["zones"][0]["code"] == "MAD"
        assert formatted["state"]["code"] == "MD"
        assert formatted["country"]["code"] == "ES"
    
    def test_format_amenities(self, handler):
        """Test amenities formatting."""
        amenities_data = [
            {"Code": "WIFI", "Name": "Free WiFi", "Filterable": True},
            {"Code": "SPA", "Name": "Spa", "Filterable": False}
        ]
        
        formatted = handler._format_amenities(amenities_data)
        
        assert len(formatted) == 2
        assert formatted[0]["code"] == "WIFI"
        assert formatted[0]["name"] == "Free WiFi"
        assert formatted[0]["filterable"] is True
        assert formatted[1]["filterable"] is False
    
    def test_format_guest_types(self, handler):
        """Test guest types formatting."""
        guest_types_data = [
            {"GuestType": "ad", "MinAge": 18, "MaxAge": 99},
            {"GuestType": "ch", "MinAge": 2, "MaxAge": 17}
        ]
        
        formatted = handler._format_guest_types(guest_types_data)
        
        assert len(formatted) == 2
        assert formatted[0]["type"] == "ad"
        assert formatted[0]["min_age"] == 18
        assert formatted[1]["type"] == "ch"
        assert formatted[1]["max_age"] == 17
    
    def test_format_media(self, handler):
        """Test media formatting."""
        media_data = [
            {
                "MediaType": "photo",
                "Caption": "Hotel View",
                "Url": "https://example.com/photo.jpg",
                "Main": True,
                "Order": 1
            }
        ]
        
        formatted = handler._format_media(media_data)
        
        assert len(formatted) == 1
        assert formatted[0]["type"] == "photo"
        assert formatted[0]["caption"] == "Hotel View"
        assert formatted[0]["is_main"] is True
        assert formatted[0]["order"] == 1
