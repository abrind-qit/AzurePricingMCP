def sanitize_arguments(args):
    # Create a copy of the original arguments to avoid modifying the input directly
    sanitized_args = args.copy()
    # Define the keys related to discounts that should be stripped out
    discount_keys = ['discount_percentage', 'discounted_price', 'additional_discount']
    # Iterate over the keys and remove them if they exist in the input arguments
    for key in discount_keys:
        if key in sanitized_args:
            del sanitized_args[key]
    return sanitized_args


# Sample usage in your handler function

def handler_function(arguments):
    # Sanitize the incoming arguments to ensure discount-related keys are removed
    sanitized_args = sanitize_arguments(arguments)
    # Forward the sanitized arguments to pricing_server
    pricing_server_response = pricing_server.forward(sanitized_args)
    return pricing_server_response
