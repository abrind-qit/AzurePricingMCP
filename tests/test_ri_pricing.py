import pytest
from unittest.mock import AsyncMock, MagicMock
from azure_pricing_mcp.server import AzurePricingServer


@pytest.mark.asyncio
async def test_get_ri_pricing():
    server = AzurePricingServer()
    server._make_request = AsyncMock()

    # Mock RI response
    server._make_request.side_effect = [
        {
            "Items": [
                {
                    "skuName": "D4s v3",
                    "armRegionName": "eastus",
                    "retailPrice": 3504.0,  # Total cost for 1 year (approx 0.4/hr * 8760)
                    "reservationTerm": "1 Year",
                    "unitOfMeasure": "1 Hour",
                }
            ]
        },
        {
            "Items": [
                {
                    "skuName": "D4s v3",
                    "armRegionName": "eastus",
                    "retailPrice": 0.8,
                    "priceType": "Consumption",
                    "unitOfMeasure": "1 Hour",
                }
            ]
        },
    ]

    result = await server.get_ri_pricing(
        service_name="Virtual Machines", sku_name="D4s v3", region="eastus", compare_on_demand=True
    )

    assert len(result["ri_items"]) == 1
    assert "comparison" in result
    comp = result["comparison"][0]
    assert comp["sku"] == "D4s v3"

    # RI Hourly = 3504 / 8760 = 0.4
    # OD Hourly = 0.8
    # Savings = (0.8 - 0.4) / 0.8 = 50%
    assert comp["savings_percentage"] == 50.0

    # Break-even: Total RI (3504) / Monthly OD (0.8 * 730 = 584) = 6.0 months
    assert comp["break_even_months"] == 6.0
