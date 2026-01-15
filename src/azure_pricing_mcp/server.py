#!/usr/bin/env python3
"""
Azure Pricing MCP Server

A Model Context Protocol server that provides tools for querying Azure retail pricing.
"""

import asyncio
import logging
import os
from typing import Any

import aiohttp
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Azure Retail Prices API configuration
AZURE_PRICING_BASE_URL = "https://prices.azure.com/api/retail/prices"
DEFAULT_API_VERSION = "2023-01-01-preview"
MAX_RESULTS_PER_REQUEST = 1000

# Retry and rate limiting configuration
MAX_RETRIES = 3
RATE_LIMIT_RETRY_BASE_WAIT = 5  # seconds

# Common service name mappings for fuzzy search
# Maps user-friendly terms to official Azure service names
SERVICE_NAME_MAPPINGS = {
    "app service": "Azure App Service",
    "web app": "Azure App Service",
    "virtual machine": "Virtual Machines",
    "storage": "Storage",
    "sql": "Azure SQL Database",
    "cosmos": "Azure Cosmos DB",
    "functions": "Azure Functions",
}


def normalize_sku_name(sku_name: str) -> tuple[list[str], str]:
    if not sku_name:
        return ([], "")

    original = sku_name.strip()
    normalized = original

    prefixes_to_remove = ["Standard_", "Basic_", "standard_", "basic_"]
    for prefix in prefixes_to_remove:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break

    display_name = normalized.replace("_", " ")

    search_terms = []
    undersore_variant = normalized.replace(" ", "_")
    if undersore_variant not in search_terms:
        search_terms.append(undersore_variant)

    space_variant = normalized.replace("_", " ")
    if space_variant not in search_terms:
        search_terms.append(space_variant)

    if normalized not in search_terms:
        search_terms.append(normalized)

    return (search_terms, display_name)

class AzurePricingServer:
    def __init__(self):
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _make_request(self, url: str, params: dict[str, Any] | None = None, max_retries: int = MAX_RETRIES) -> dict[str, Any]:
        if not self.session:
            raise RuntimeError("HTTP session not initialized")

        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                async with self.session.get(url, params=params) as response:
                    response.raise_for_status()
                    json_data: dict[str, Any] = await response.json()
                    return json_data

            except aiohttp.ClientResponseError as e:
                logger.error(f"HTTP request failed: {e}")
                raise
            except aiohttp.ClientError as e:
                logger.error(f"HTTP request failed: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error during request: {e}")
                raise

        if last_exception:
            raise last_exception
        raise RuntimeError("Request failed without exception")

    async def search_azure_prices(
        self,
        service_name: str | None = None,
        region: str | None = None,
        sku_name: str | None = None,
        currency_code: str = "USD",
        limit: int = 50,
    ) -> dict[str, Any]:
        filter_conditions = []

        if service_name:
            filter_conditions.append(f"serviceName eq '{service_name}'")
        if region:
            filter_conditions.append(f"armRegionName eq '{region}'")
        if sku_name:
            filter_conditions.append(f"contains(skuName, '{sku_name}')")

        params = {"api-version": DEFAULT_API_VERSION, "currencyCode": currency_code}

        if filter_conditions:
            params["$filter"] = " and ".join(filter_conditions)

        if limit < MAX_RESULTS_PER_REQUEST:
            params["$top"] = str(limit)

        data = await self._make_request(AZURE_PRICING_BASE_URL, params)
        items = data.get("Items", [])

        if len(items) > limit:
            items = items[:limit]

        result = {
            "items": items,
            "count": len(items) if isinstance(items, list) else 0,
            "has_more": bool(data.get("NextPageLink")),
            "currency": currency_code,
            "filters_applied": filter_conditions,
        }

        return result

    async def compare_prices(self, service_name: str, sku_name: str | None = None, regions: list[str] | None = None, currency_code: str = "USD", limit: int = 50) -> dict[str, Any]:
        comparisons = []

        if regions and isinstance(regions, list):
            for region in regions:
                try:
                    result = await self.search_azure_prices(service_name=service_name, sku_name=sku_name, region=region, currency_code=currency_code, limit=10)
                    if result["items"]:
                        item = result["items"][0]
                        comparisons.append({"region": region, "sku_name": item.get("skuName"), "retail_price": item.get("retailPrice"), "product_name": item.get("productName")})
                except Exception as e:
                    logger.warning(f"Failed to get prices for region {region}: {e}")
        else:
            result = await self.search_azure_prices(service_name=service_name, currency_code=currency_code, limit=20)
            sku_prices = {}
            items = result.get("items", [])
            for item in items:
                sku = item.get("skuName")
                if sku and sku not in sku_prices:
                    sku_prices[sku] = {"sku_name": sku, "retail_price": item.get("retailPrice"), "product_name": item.get("productName")}  
            comparisons = list(sku_prices.values())

        comparisons.sort(key=lambda x: x.get("retail_price", 0))

        result = {
            "comparisons": comparisons,
            "service_name": service_name,
            "currency": currency_code,
            "comparison_type": "regions" if regions else "skus",
        }

        return result

    async def recommend_regions(self, service_name: str, sku_name: str, top_n: int = 10, currency_code: str = "USD") -> dict[str, Any]:
        return {"message": "Recommendations not implemented yet."}  


def create_server() -> Server:
    server = Server("azure-pricing")
    pricing_server = AzurePricingServer()

    @server.list_tools()
    async def handle_list_tools() -> list[Tool]:
        return [
            Tool(name="azure_price_search", description="Search Azure retail prices with various filters"),
            Tool(name="azure_price_compare", description="Compare Azure prices across regions or SKUs")
        ]

    return server


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Azure Pricing MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    args, _ = parser.parse_known_args()

    server = create_server()

    if args.transport == "http":
        from starlette.applications import Starlette
        from starlette.requests import Request
        from starlette.responses import Response
        return
    else:
        return

