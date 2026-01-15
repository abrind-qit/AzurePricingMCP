# Usage Examples

## Example 1: Retrieve Pricing

To retrieve pricing for a specific Azure service, send a request without any applied discounts. The response will include raw retail prices.

### Request
```
GET /api/pricing/azure-service
```

### Response
```json
{
    "service": "Azure Compute",
    "pricing": {
        "retail_price": "100.00"
    }
}
```

## Example 2: Retrieve Additional Services

Here’s how to get pricing for additional services without any discounts applied:

### Request
```
GET /api/pricing/azure-additional-services
```

### Response
```json
{
    "services": [
        {
            "service": "Azure Storage",
            "retail_price": "50.00"
        },
        {
            "service": "Azure Backup",
            "retail_price": "30.00"
        }
    ]
}
```

## Important Notes
- Ensure you are aware of the retail prices as they may vary based on location and Azure region.