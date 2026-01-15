#!/usr/bin/env python3
"""Tool handlers for Azure Pricing MCP Server."""

import json
import logging
from typing import Any

from mcp.types import TextContent

logger = logging.getLogger(__name__)

def register_tool_handlers(server: Any, pricing_server: Any) -> None:
    """Register all tool call handlers with the server.

    Args:
        server: The MCP server instance
        pricing_server: The AzurePricingServer instance
    """

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool calls."""

        try:
            async with pricing_server:
                if name == "azure_price_search":
                    return await _handle_price_search(pricing_server, arguments)

                elif name == "azure_price_compare":
                    return await _handle_price_compare(pricing_server, arguments)

                elif name == "azure_cost_estimate":
                    return await _handle_cost_estimate(pricing_server, arguments)

                elif name == "azure_discover_skus":
                    return await _handle_discover_skus(pricing_server, arguments)

                elif name == "azure_sku_discovery":
                    return await _handle_sku_discovery(pricing_server, arguments)

                elif name == "azure_region_recommend":
                    return await _handle_region_recommend(pricing_server, arguments)

                elif name == "azure_ri_pricing":
                    return await _handle_ri_pricing(pricing_server, arguments)

                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except Exception as e:
            logger.error(f"Error handling tool call {name}: {e}")
            return [TextContent(type="text", text=f"Error: {str(e)}")]


async def _handle_price_search(pricing_server, arguments: dict) -> list[TextContent]:
    """Handle azure_price_search tool calls."""
    result = await pricing_server.search_azure_prices(**arguments)

    # Format the response
    if result.get("items"):
        formatted_items = []
        for item in result["items"]:
            formatted_item = {
                "service": item.get("serviceName"),
                "product": item.get("productName"),
                "sku": item.get("skuName"),
                "region": item.get("armRegionName"),
                "location": item.get("location"),
                "price": item.get("retailPrice"),
                "unit": item.get("unitOfMeasure"),
                "type": item.get("type"),
                "savings_plans": item.get("savingsPlan", []),
            }

            # Preserve originalPrice if present but do not present discount calculations
            if "originalPrice" in item:
                formatted_item["original_price"] = item.get("originalPrice")

            formatted_items.append(formatted_item)

        if result.get("count", 0) > 0:
            response_text = f"Found {result['count']} Azure pricing results:\n\n"

            # Add SKU validation info if present
            if "sku_validation" in result:
                validation = result["sku_validation"]
                response_text += f"⚠️ SKU Validation: {validation['message']}\n"
                if validation["suggestions"]:
                    response_text += "🔍 Suggested SKUs:\n"
                    for suggestion in validation["suggestions"][:3]:
                        response_text += (
                            f"   • {suggestion['sku_name']}: ${suggestion['price']} per {suggestion['unit']}\n"
                        )
                    response_text += "\n"

            # Add clarification info if present
            if "clarification" in result:
                clarification = result["clarification"]
                response_text += f"ℹ️ {clarification['message']}\n"
                if clarification["suggestions"]:
                    response_text += "Top matches:\n"
                    for suggestion in clarification["suggestions"]:
                        response_text += f"   • {suggestion}\n"
                    response_text += "\n"

            response_text += "**Detailed Pricing:**\n"
            response_text += json.dumps(formatted_items, indent=2)

            return [TextContent(type="text", text=response_text)]
        else:
            response_text = "No valid pricing results found."
            return [TextContent(type="text", text=response_text)]
    else:
        response_text = "No pricing results found for the specified criteria."

        # Add SKU validation info if present
        if "sku_validation" in result:
            validation = result["sku_validation"]
            response_text += f"\n\n⚠️ {validation['message']}\n"
            if validation["suggestions"]:
                response_text += "\n🔍 Did you mean one of these SKUs?\n"
                for suggestion in validation["suggestions"][:5]:
                    response_text += f"   • {suggestion['sku_name']}: ${suggestion['price']} per {suggestion['unit']}"
                    if suggestion["region"]:
                        response_text += f" (in {suggestion['region']})"
                    response_text += "\n"

        return [TextContent(type="text", text=response_text)]


async def _handle_price_compare(pricing_server, arguments: dict) -> list[TextContent]:
    """Handle azure_price_compare tool calls."""
    result = await pricing_server.compare_prices(**arguments)

    response_text = f"Price comparison for {result.get('service_name', 'N/A')}:\n\n"

    response_text += json.dumps(result.get("comparisons", []), indent=2)

    return [TextContent(type="text", text=response_text)]


async def _handle_region_recommend(pricing_server, arguments: dict) -> list[TextContent]:
    """Handle azure_region_recommend tool calls."""
    result = await pricing_server.recommend_regions(**arguments)

    # Check for errors
    if "error" in result:
        return [TextContent(type="text", text=f"Error: {result['error']}")]

    recommendations = result.get("recommendations", [])
    if not recommendations:
        return [TextContent(type="text", text="No region recommendations found for the specified criteria.")]

    # Build response text
    response_text = f"🌍 Region Recommendations for {result.get('service_name', 'N/A')} - {result.get('sku_name', '')}\n\n"
    response_text += f"Currency: {result.get('currency')}\n"
    response_text += f"Total regions found: {result.get('total_regions_found')}\n"
    response_text += f"Showing top: {result.get('showing_top')}\n"

    # Add summary
    if "summary" in result:
        summary = result["summary"]
        response_text += f"\n📊 Summary:\n   🥇 Cheapest: {summary.get('cheapest_location')} ({summary.get('cheapest_region')}) - ${summary.get('cheapest_price'):.6f}\n"

    # Build recommendations table
    response_text += "\n📋 Ranked Recommendations (On-Demand Pricing):\n\n"
    response_text += "| Rank | Region | Location | On-Demand Price | Spot Price | Savings vs Max |\n"
    response_text += "|------|--------|----------|-----------------|------------|----------------|\n"

    for i, rec in enumerate(recommendations, 1):
        region = rec.get("region", "N/A")
        location = rec.get("location", "N/A")
        price = rec.get("retail_price", 0)
        savings = rec.get("savings_vs_most_expensive", 0)
        unit = rec.get("unit_of_measure", "")
        spot_price = rec.get("spot_price")

        rank_display = {1: "🥇 1", 2: "🥈 2", 3: "🥉 3"}.get(i, str(i))
        spot_display = f"${spot_price:.6f}" if spot_price else "N/A"

        response_text += (
            f"| {rank_display} | {region} | {location} | ${price:.6f}/{unit} | {spot_display} | {savings:.1f}% |\n"
        )

    return [TextContent(type="text", text=response_text)]


async def _handle_cost_estimate(pricing_server, arguments: dict) -> list[TextContent]:
    """Handle azure_cost_estimate tool calls."""
    result = await pricing_server.estimate_costs(**arguments)

    if "error" in result:
        return [TextContent(type="text", text=f"Error: {result['error']}")]

    # Format cost estimate
    estimate_text = f"""
Cost Estimate for {result.get('service_name', '')} - {result.get('sku_name', '')}\nRegion: {result.get('region', '')}\nProduct: {result.get('product_name', '')}\nUnit: {result.get('unit_of_measure', '')}\nCurrency: {result.get('currency', '')}\n"""

    estimate_text += f"""
Usage Assumptions:\n- Hours per month: {result.get('usage_assumptions', {}).get('hours_per_month')}\n- Hours per day: {result.get('usage_assumptions', {}).get('hours_per_day')}\n
On-Demand Pricing:\n- Hourly Rate: ${result.get('on_demand_pricing', {}).get('hourly_rate')}\n- Daily Cost: ${result.get('on_demand_pricing', {}).get('daily_cost')}\n- Monthly Cost: ${result.get('on_demand_pricing', {}).get('monthly_cost')}\n- Yearly Cost: ${result.get('on_demand_pricing', {}).get('yearly_cost')}\n"""

    if result.get('savings_plans'):
        estimate_text += "\nSavings Plans Available:\n"
        for plan in result['savings_plans']:
            estimate_text += f"\n{plan.get('term')} Term:\n- Hourly Rate: ${plan.get('hourly_rate')}\n- Monthly Cost: ${plan.get('monthly_cost')}\n- Yearly Cost: ${plan.get('yearly_cost')}\n- Savings: {plan.get('savings_percent')}% (${plan.get('annual_savings')} annually)\n"

    return [TextContent(type="text", text=estimate_text)]


async def _handle_discover_skus(pricing_server, arguments: dict) -> list[TextContent]:
    """Handle azure_discover_skus tool calls."""
    result = await pricing_server.discover_skus(**arguments)

    skus = result.get("skus", [])
    if skus:
        return [
            TextContent(
                type="text",
                text=f"Found {result.get('total_skus', 0)} SKUs for {result.get('service_name', '')}:\n\n" + json.dumps(skus, indent=2),
            )
        ]
    else:
        return [TextContent(type="text", text="No SKUs found for the specified service.")]    


async def _handle_sku_discovery(pricing_server, arguments: dict) -> list[TextContent]:
    """Handle azure_sku_discovery tool calls."""
    result = await pricing_server.discover_service_skus(**arguments)

    if result.get("service_found"):
        service_name = result.get("service_found")
        original_search = result.get("original_search")
        skus = result.get("skus")
        total_skus = result.get("total_skus")
        match_type = result.get("match_type", "exact")

        response_text = f"SKU Discovery for '{original_search}'"

        if match_type == "exact_mapping":
            response_text += f" (mapped to: {service_name})"

        response_text += f"\n\nFound {total_skus} SKUs for {service_name}:\n\n"

        products: dict[str, list[tuple]] = {}
        for sku_name, sku_data in skus.items():
            product = sku_data["product_name"]
            if product not in products:
                products[product] = []
            products[product].append((sku_name, sku_data))

        for product, product_skus in products.items():
            response_text += f"📦 {product}:\n"
            for sku_name, sku_data in sorted(product_skus)[:10]:
                min_price = sku_data.get("min_price", 0)
                unit = sku_data.get("sample_unit", "Unknown")
                region_count = len(sku_data.get("regions", []))

                response_text += f"   • {sku_name}\n"
                response_text += f"     Price: ${min_price} per {unit}"
                if region_count > 1:
                    response_text += f" (available in {region_count} regions)"
                response_text += "\n"
            response_text += "\n"

        return [TextContent(type="text", text=response_text)]
    else:
        suggestions = result.get("suggestions", [])
        original_search = result.get("original_search")

        if suggestions:
            response_text = f"No exact match found for '{original_search}'\n\n"
            response_text += "🔍 Did you mean one of these services?\n\n"

            for i, suggestion in enumerate(suggestions[:5], 1):
                service_name = suggestion.get("service_name")
                match_reason = suggestion.get("match_reason")
                sample_items = suggestion.get("sample_items")

                response_text += f"{i}. {service_name}\n"
                response_text += f"   Reason: {match_reason}\n"

                if sample_items:
                    response_text += "   Sample SKUs:\n"
                    for item in sample_items[:3]:
                        sku = item.get("skuName", "Unknown")
                        price = item.get("retailPrice", 0)
                        unit = item.get("unitOfMeasure", "Unknown")
                        response_text += f"     • {sku}: ${price} per {unit}\n"
                response_text += "\n"

            response_text += "💡 Try using one of the exact service names above."
        else:
            response_text = f"No matches found for '{original_search}'\n\n"
            response_text += "💡 Try using terms like:\n"
            response_text += "• 'app service' or 'web app' for Azure App Service\n"
            response_text += "• 'vm' or 'virtual machine' for Virtual Machines\n"
            response_text += "• 'storage' or 'blob' for Storage services\n"
            response_text += "• 'sql' or 'database' for SQL Database\n"
            response_text += "• 'kubernetes' or 'aks' for Azure Kubernetes Service"\n"

        return [TextContent(type="text", text=response_text)]
