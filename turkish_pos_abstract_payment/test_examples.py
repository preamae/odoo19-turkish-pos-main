"""
Test examples for Turkish POS Abstract Payment module.

These examples demonstrate how to use the payment methods and gateways
programmatically.
"""

# Example 1: Get available payment methods
def example_get_payment_methods(env):
    """Get all available payment methods."""
    PaymentMethod = env['payment.method']
    
    # Get all active methods
    methods = PaymentMethod.search([('active', '=', True)])
    
    print("Available Payment Methods:")
    for method in methods:
        print(f"  - {method.name} ({method.code})")
        print(f"    Type: {method.payment_type}")
        print(f"    Installments: {'Yes' if method.supports_installments else 'No'}")
        print(f"    3D Secure: {'Yes' if method.requires_3d_secure else 'No'}")
        print()


# Example 2: Validate payment amount
def example_validate_amount(env, method_code='credit_card', amount=100.0):
    """Validate a payment amount for a specific method."""
    PaymentMethod = env['payment.method']
    Currency = env['res.currency']
    
    method = PaymentMethod.search([('code', '=', method_code)], limit=1)
    currency = Currency.search([('name', '=', 'TRY')], limit=1)
    
    if method:
        result = method.validate_payment_amount(amount, currency)
        print(f"Validation for {amount} TRY:")
        print(f"  Success: {result['success']}")
        print(f"  Message: {result['message']}")
    else:
        print(f"Method {method_code} not found")


# Example 3: Get installment options
def example_get_installments(env, amount=1000.0, bin_number='542119'):
    """Get installment options for a card payment."""
    PaymentMethod = env['payment.method']
    Currency = env['res.currency']
    
    method = PaymentMethod.search([('code', '=', 'credit_card')], limit=1)
    currency = Currency.search([('name', '=', 'TRY')], limit=1)
    
    if method:
        installments = method.get_installment_options(
            amount=amount,
            currency=currency,
            bin_number=bin_number
        )
        
        print(f"Installment Options for {amount} TRY (BIN: {bin_number}):")
        for bank_data in installments:
            print(f"\n  Bank: {bank_data['bank']['name']}")
            for option in bank_data['installments']:
                if option['installment_count'] == 1:
                    print(f"    Peşin: {option['total_amount']:.2f} TL")
                else:
                    print(f"    {option['installment_count']} Taksit: "
                          f"{option['installment_amount']:.2f} TL x {option['installment_count']} = "
                          f"{option['total_amount']:.2f} TL "
                          f"(Faiz: %{option['interest_rate']:.2f})")


# Example 4: Initiate a payment
def example_initiate_payment(env):
    """Initiate a test payment."""
    PaymentMethod = env['payment.method']
    Currency = env['res.currency']
    
    method = PaymentMethod.search([('code', '=', 'credit_card')], limit=1)
    currency = Currency.search([('name', '=', 'TRY')], limit=1)
    
    if method:
        result = method.initiate_payment(
            amount=100.0,
            currency=currency,
            reference='TEST-PAY-001',
            card_data={
                'card_number': '4111111111111111',
                'card_holder_name': 'TEST USER',
                'expiry_month': '12',
                'expiry_year': '2025',
                'cvv': '123',
            },
            installments=1
        )
        
        print("Payment Initiation Result:")
        print(f"  Success: {result.get('success')}")
        print(f"  Message: {result.get('message')}")
        print(f"  Requires 3D: {result.get('requires_3d', False)}")
        if result.get('redirect_url'):
            print(f"  Redirect URL: {result['redirect_url']}")


# Example 5: Create a custom payment method
def example_create_payment_method(env):
    """Create a new payment method."""
    PaymentMethod = env['payment.method']
    Currency = env['res.currency']
    
    currencies = Currency.search([('name', 'in', ['TRY', 'USD', 'EUR'])])
    
    method = PaymentMethod.create({
        'name': 'Custom Payment Method',
        'code': 'custom_method',
        'payment_type': 'digital_wallet',
        'description': 'A custom digital wallet payment method',
        'sequence': 40,
        'supported_currency_ids': [(6, 0, currencies.ids)],
        'min_amount': 10.0,
        'max_amount': 50000.0,
        'supports_installments': False,
        'requires_3d_secure': False,
        'show_on_checkout': True,
        'auto_capture': True,
        'allow_refund': True,
    })
    
    print(f"Created payment method: {method.name} (ID: {method.id})")
    return method


# Example 6: Configure a gateway
def example_configure_gateway(env):
    """Configure a payment gateway."""
    Gateway = env['payment.gateway']
    
    gateway = Gateway.create({
        'name': 'Test Gateway',
        'code': 'test_gw',
        'gateway_type': 'redirect',
        'environment': 'test',
        'supports_3d_secure': True,
        'supports_installments': True,
        'supports_refunds': True,
        'timeout': 30,
        'retry_count': 3,
    })
    
    # Set credentials
    gateway.set_credentials({
        'api_key': 'test_key_123',
        'merchant_id': 'merchant_001',
        'secret': 'secret_xyz',
    })
    
    print(f"Created gateway: {gateway.name} (ID: {gateway.id})")
    print(f"Credentials: {gateway.get_credentials()}")
    return gateway


# Example 7: List methods for checkout
def example_checkout_methods(env, amount=500.0):
    """Get payment methods available for checkout."""
    PaymentMethod = env['payment.method']
    Currency = env['res.currency']
    
    currency = Currency.search([('name', '=', 'TRY')], limit=1)
    
    methods = PaymentMethod.get_payment_methods_for_checkout(
        currency=currency,
        amount=amount
    )
    
    print(f"Payment Methods for Checkout ({amount} TRY):")
    for method in methods:
        print(f"  - {method.name}")
        print(f"    Min: {method.min_amount}, Max: {method.max_amount}")


# Run all examples
def run_all_examples(env):
    """Run all example functions."""
    print("=" * 70)
    print("Turkish POS Abstract Payment - Test Examples")
    print("=" * 70)
    print()
    
    print("1. Getting available payment methods...")
    example_get_payment_methods(env)
    print()
    
    print("2. Validating payment amount...")
    example_validate_amount(env)
    print()
    
    print("3. Getting installment options...")
    example_get_installments(env)
    print()
    
    print("4. Initiating a payment...")
    example_initiate_payment(env)
    print()
    
    print("5. Creating custom payment method...")
    # example_create_payment_method(env)  # Commented to avoid DB changes
    print("  (Skipped - would create new record)")
    print()
    
    print("6. Configuring gateway...")
    # example_configure_gateway(env)  # Commented to avoid DB changes
    print("  (Skipped - would create new record)")
    print()
    
    print("7. Listing checkout methods...")
    example_checkout_methods(env)
    print()
    
    print("=" * 70)
    print("Examples completed!")
    print("=" * 70)


# To run in Odoo shell:
# $ odoo-bin shell -c odoo.conf -d your_database
# >>> from odoo import SUPERUSER_ID
# >>> env = api.Environment(cr, SUPERUSER_ID, {})
# >>> exec(open('test_examples.py').read())
# >>> run_all_examples(env)
