# Turkish POS Abstract Payment Module

**Version:** 19.0.1.0.0  
**Author:** Turkish POS Team  
**License:** LGPL-3

## Overview

Turkish POS Abstract Payment is a comprehensive, extensible payment infrastructure module for Odoo 19. It provides an abstract base for payment methods with full Turkish POS integration, multi-currency support, and modern payment flow implementation.

## Features

### Core Features
- ✅ **Abstract Payment Method Model** - Extensible base class for all payment methods
- ✅ **Concrete Payment Methods** - Cash, Credit Card, and Bank Transfer implementations
- ✅ **Multi-Currency Support** - TRY, USD, EUR and more
- ✅ **Modern Odoo 19 Integration** - Full `_processDirectFlow` implementation
- ✅ **3D Secure Flow** - Complete redirect-based authentication flow
- ✅ **BIN Detection** - Automatic bank detection from card numbers
- ✅ **Installment Support** - Turkish POS bank installment integration
- ✅ **Gateway Management** - Flexible gateway configuration with credentials
- ✅ **Null-Guarded JavaScript** - Robust frontend with error handling
- ✅ **Turkish Language** - Full Turkish translation (tr.po)

### Payment Methods Included

#### 1. Cash Payment (Nakit Ödeme)
- Simple cash payment for in-person transactions
- Configurable amount limits
- Full refund support

#### 2. Credit Card Payment (Kredi Kartı)
- Credit/debit card payments
- Installment support (up to 12 installments)
- 3D Secure authentication
- BIN-based bank detection
- Dynamic installment calculation
- Turkish POS bank integration

#### 3. Bank Transfer (Banka Havalesi / EFT)
- Bank wire transfer payments
- Manual confirmation workflow
- Bank account details display
- Delayed payment processing

### Technical Features

#### Backend (Python)
- **Abstract Model Pattern** - Clean inheritance structure
- **Validation Framework** - Amount, currency, and data validation
- **Gateway Integration** - Pluggable gateway architecture
- **Transaction Management** - Reference tracking and status management
- **Error Handling** - Comprehensive try/catch and logging

#### Frontend (JavaScript)
- **Modern Odoo 19 JS** - Uses `@web/legacy/js/public/public_widget`
- **RPC Integration** - Clean `/payment/abstract/*` endpoints
- **Null Guards** - All DOM access protected against null errors
- **Card Preview** - Live card number formatting and display
- **Installment Loading** - Async BIN-based installment fetch
- **Form Validation** - Turkish error messages
- **3D Secure Handling** - Automatic redirect and callback processing

#### Controllers (HTTP/JSON)
- `GET/POST /payment/abstract/methods` - List available methods
- `POST /payment/abstract/installments` - Get installment options
- `POST /payment/abstract/initiate` - Start payment
- `POST /payment/abstract/validate` - Validate payment data
- `GET/POST /payment/abstract/3d_secure` - 3D Secure page
- `GET/POST /payment/abstract/3d_return` - 3D callback handler

## Installation

### Prerequisites
- Odoo 19.0
- Python 3.10+
- **Turkish POS module** (`turkish_pos`) - Must be installed first
- Base Odoo modules: `base`, `payment`, `website_sale`, `product`, `sale`, `web`

### Steps

**Important:** The Turkish POS (`turkish_pos`) module must be installed before installing this module.

1. **Install Turkish POS module first:**
   ```bash
   # If not already installed
   cd /opt/odoo/addons
   # Ensure turkish_pos module is present
   # Install it via Odoo Apps interface
   ```

2. **Copy module to addons directory:**
   ```bash
   cd /opt/odoo/addons
   cp -r /path/to/turkish_pos_abstract_payment .
   ```

3. **Restart Odoo:**
   ```bash
   sudo systemctl restart odoo
   # or
   ./odoo-bin -c odoo.conf --stop-after-init -u all
   ```

4. **Update Apps List:**
   - Go to **Apps** menu
   - Click **Update Apps List**
   - Search for "Turkish POS Abstract Payment"
   - Click **Install**

4. **Verify Installation:**
   - Check menu: **Abstract Payment > Payment Methods**
   - You should see 3 default methods: Cash, Credit Card, Bank Transfer

## Configuration

### 1. Payment Methods Configuration

Navigate to **Abstract Payment > Payment Methods**

#### Configure Credit Card Method:
1. Open **Kredi Kartı** payment method
2. **General Tab:**
   - Set description (shown to customers)
   - Select gateway (Dummy Gateway for testing)

3. **Currency & Limits Tab:**
   - Add supported currencies (TRY, USD, EUR)
   - Set min/max amounts

4. **Installments Tab:**
   - Set `Max Installments` (e.g., 12)
   - Set `Min Installment Amount` (e.g., 100 TL)
   - Link Turkish POS banks (if available)

5. **Transaction Settings Tab:**
   - Enable `Auto Capture` for immediate payment
   - Configure refund policy

#### Configure Cash Method:
1. Open **Nakit Ödeme** payment method
2. Set `Max Amount` for cash payments (e.g., 10,000 TL)
3. Configure supported currencies

#### Configure Bank Transfer Method:
1. Open **Banka Havalesi / EFT** payment method
2. Add bank account details (IBAN, SWIFT, etc.)
3. Set transfer instructions for customers

### 2. Payment Gateway Configuration

Navigate to **Abstract Payment > Payment Gateways**

#### Configure Dummy Gateway (Test):
1. Open **Dummy Gateway (Test)**
2. **Credentials Tab:**
   ```json
   {
     "api_key": "test_api_key_12345",
     "merchant_id": "test_merchant_001",
     "secret_key": "test_secret_xyz",
     "terminal_id": "VP000001"
   }
   ```
3. **URLs Tab:**
   - Payment URL: `https://test-gateway.example.com/payment`
   - Callback URL: `/payment/abstract/3d_return`

4. Set **Environment** to `Test` for sandbox mode

#### Add Production Gateway:
1. Click **Create**
2. Fill in:
   - Name: Your gateway name (e.g., "Param", "iyzico")
   - Code: Unique code (e.g., "param", "iyzico")
   - Gateway Type: Select based on gateway
   - Environment: Production
3. Add credentials in JSON format
4. Configure URLs and timeouts
5. Save

### 3. Currency Configuration

Make sure required currencies are active:

1. Go to **Settings > General Settings > Multi-Currencies**
2. Enable **Multi-Currencies**
3. Activate: **TRY**, **USD**, **EUR**
4. Set exchange rates

## Usage

### For Developers

#### Creating a Custom Payment Method

```python
from odoo import models, fields

class PaymentMethodCustom(models.Model):
    _name = 'payment.method.custom'
    _inherit = 'payment.method'
    
    # Add custom fields
    custom_field = fields.Char(string='Custom Field')
    
    def initiate_payment(self, amount, currency, reference, **kwargs):
        """Override to implement custom payment logic."""
        # Your custom implementation
        return {
            'success': True,
            'message': 'Payment initiated',
        }
```

#### Extending the Gateway

```python
from odoo import models

class PaymentGateway(models.Model):
    _inherit = 'payment.gateway'
    
    def initiate_payment(self, amount, currency, card_data, reference, **kwargs):
        """Override for custom gateway."""
        if self.code == 'my_gateway':
            return self._initiate_my_gateway_payment(
                amount, currency, card_data, reference, **kwargs
            )
        return super().initiate_payment(
            amount, currency, card_data, reference, **kwargs
        )
```

#### Using in Controllers

```python
from odoo import http
from odoo.http import request

class MyController(http.Controller):
    @http.route('/my/payment', type='http', auth='public', website=True)
    def my_payment_page(self, **kwargs):
        # Get available payment methods
        PaymentMethod = request.env['payment.method'].sudo()
        methods = PaymentMethod.get_payment_methods_for_checkout(
            currency=request.env.ref('base.TRY'),
            amount=100.00
        )
        
        return request.render('my_module.payment_page', {
            'methods': methods,
        })
```

### For Users

#### Making a Payment (Frontend)

1. **Test Payment Page:**
   - Navigate to: `http://yoursite.com/payment/abstract/test`
   - This is a test page for trying the payment flow

2. **Select Payment Method:**
   - Choose from available methods (Cash, Card, Transfer)

3. **For Card Payments:**
   - Enter card number (16 digits)
   - BIN detection happens at 6 digits
   - Card preview updates in real-time
   - Installment options load automatically
   - Select installment option
   - Enter CVV and expiry date
   - Click "Ödemeyi Tamamla" (Complete Payment)

4. **3D Secure Flow:**
   - Form redirects to 3D Secure page (test mode)
   - Approve or cancel payment
   - Returns to success/error page

#### Test Card Numbers (Dummy Gateway)

For testing, use these simulated cards:

- **Visa:** 4111 1111 1111 1111
- **Mastercard:** 5500 0000 0000 0004
- **Troy:** 9792 0000 0000 0000

- **CVV:** Any 3 digits (e.g., 123)
- **Expiry:** Any future date

## API Reference

### JSON Endpoints

#### Get Payment Methods
```bash
curl -X POST http://yoursite.com/payment/abstract/methods \
  -H "Content-Type: application/json" \
  -d '{"amount": 100, "currency_id": 1}'
```

**Response:**
```json
{
  "success": true,
  "methods": [
    {
      "id": 1,
      "name": "Kredi Kartı",
      "code": "credit_card",
      "payment_type": "card",
      "supports_installments": true,
      "requires_3d_secure": true
    }
  ]
}
```

#### Get Installment Options
```bash
curl -X POST http://yoursite.com/payment/abstract/installments \
  -H "Content-Type: application/json" \
  -d '{
    "method_id": 1,
    "amount": 1000,
    "currency_id": 1,
    "bin_number": "542119"
  }'
```

**Response:**
```json
{
  "success": true,
  "installments": [
    {
      "bank": {"id": 1, "name": "Test Bank", "code": "TEST"},
      "installments": [
        {
          "installment_count": 1,
          "installment_amount": 1000.00,
          "total_amount": 1000.00,
          "interest_rate": 0.0,
          "is_campaign": false
        },
        {
          "installment_count": 3,
          "installment_amount": 340.00,
          "total_amount": 1020.00,
          "interest_rate": 2.0,
          "is_campaign": false
        }
      ]
    }
  ]
}
```

#### Initiate Payment
```bash
curl -X POST http://yoursite.com/payment/abstract/initiate \
  -H "Content-Type: application/json" \
  -d '{
    "method_id": 1,
    "amount": 100,
    "currency_id": 1,
    "reference": "PAY-12345",
    "card_data": {
      "card_number": "4111111111111111",
      "card_holder_name": "JOHN DOE",
      "expiry_month": "12",
      "expiry_year": "2025",
      "cvv": "123"
    },
    "installments": 1
  }'
```

**Response:**
```json
{
  "success": true,
  "requires_3d": true,
  "redirect_url": "/payment/abstract/3d_secure?ref=PAY-12345",
  "transaction_id": "DUMMY-PAY-12345",
  "message": "Redirecting to 3D Secure authentication..."
}
```

## Testing

### Manual Testing

#### Test Payment Flow:

1. **Access Test Page:**
   ```
   http://localhost:8069/payment/abstract/test
   ```

2. **Test Cash Payment:**
   - Select "Nakit Ödeme"
   - Submit form
   - Should show success without card form

3. **Test Card Payment:**
   - Select "Kredi Kartı"
   - Enter test card: 4111 1111 1111 1111
   - Watch BIN detection at 6 digits
   - See installment options load
   - Submit and complete 3D Secure

4. **Test Bank Transfer:**
   - Select "Banka Havalesi / EFT"
   - See bank account details
   - Note manual confirmation requirement

#### Test Error Handling:

1. **Invalid Card Number:**
   - Enter: "1234"
   - Should show: "Kart numarası 13-19 rakam olmalıdır"

2. **Missing CVV:**
   - Leave CVV empty
   - Should show: "CVV gerekli"

3. **Amount Below Minimum:**
   - Try amount < 10 TL for credit card
   - Should show: "Payment amount (X) is below the minimum (10.00)"

### Automated Testing

#### Unit Tests (Python):

```python
# In tests/test_payment_method.py
from odoo.tests import TransactionCase

class TestPaymentMethod(TransactionCase):
    def setUp(self):
        super().setUp()
        self.PaymentMethod = self.env['payment.method']
        self.currency_try = self.env.ref('base.TRY')
    
    def test_validate_amount(self):
        """Test payment amount validation."""
        method = self.PaymentMethod.search([('code', '=', 'credit_card')])
        
        # Valid amount
        result = method.validate_payment_amount(100, self.currency_try)
        self.assertTrue(result['success'])
        
        # Invalid amount (below minimum)
        result = method.validate_payment_amount(5, self.currency_try)
        self.assertFalse(result['success'])
```

#### Integration Tests (JavaScript):

```javascript
// Test payment form initialization
QUnit.test('AbstractPaymentForm initializes correctly', async function(assert) {
    const form = new AbstractPaymentForm();
    await form.start();
    
    assert.ok(form._amount >= 0, 'Amount should be loaded');
    assert.ok(form._currencyId, 'Currency should be set');
});
```

## Troubleshooting

### Common Issues

#### 1. "Cannot read properties of null (reading 'setAttribute')"
**Solution:** This module has null-guards on all DOM access. Check JavaScript console for actual error source.

#### 2. Payment methods not showing
**Solution:**
- Verify methods are active: `Abstract Payment > Payment Methods`
- Check `show_on_checkout` is enabled
- Verify currency is supported

#### 3. Installments not loading
**Solution:**
- Check Turkish POS module is installed (if using Turkish POS integration)
- Verify `turkish_pos_enabled` is True
- Check `turkish_pos_bank_ids` are configured
- Review browser console for JavaScript errors

#### 4. 3D Secure redirect fails
**Solution:**
- Verify gateway is active
- Check gateway URLs are configured
- Review gateway credentials
- Check Odoo logs: `grep -i "3d secure" odoo.log`

### Debug Mode

Enable debug mode for detailed logging:

1. **Odoo Configuration:**
   ```ini
   [options]
   log_level = debug
   log_handler = :DEBUG,odoo.addons.turkish_pos_abstract_payment:DEBUG
   ```

2. **JavaScript Console:**
   - Open browser DevTools (F12)
   - Check Console tab for errors
   - Check Network tab for failed requests

3. **Python Logging:**
   ```python
   import logging
   _logger = logging.getLogger(__name__)
   _logger.debug("Debug message here")
   ```

## Development Roadmap

### Planned Features
- [ ] Saved cards / tokenization
- [ ] Recurring payments / subscriptions
- [ ] Additional gateways (Param, iyzico, Tosla)
- [ ] POS (Point of Sale) integration
- [ ] Mobile app support
- [ ] Advanced fraud detection
- [ ] Payment analytics dashboard
- [ ] Webhook support for async notifications

### Integration Options
- Turkish POS module (already compatible)
- Website Sale
- Point of Sale (POS)
- Mobile apps via JSON API
- Third-party eCommerce platforms

## Security Considerations

### Best Practices
1. **Never log sensitive data** - Card numbers, CVV, etc.
2. **Use HTTPS** - Always use SSL/TLS in production
3. **PCI Compliance** - For card payments, consider PCI DSS requirements
4. **Gateway credentials** - Store securely, rotate regularly
5. **3D Secure** - Always enable for production card payments
6. **Input validation** - All inputs validated server-side
7. **CSRF protection** - Enabled on sensitive endpoints

### Data Protection
- Card numbers are NOT stored in database
- Only masked numbers stored (e.g., "****1234")
- CVV never stored
- Gateway responses logged without sensitive data

## Support

### Documentation
- **Module README:** This file
- **Inline Documentation:** All Python/JS files have docstrings
- **Turkish Translation:** Full Turkish in `i18n/tr.po`

### Getting Help
- **GitHub Issues:** Report bugs and request features
- **Odoo Community:** Post questions on Odoo forums
- **Email:** Contact module maintainers

### Contributing
Contributions welcome! Please:
1. Fork the repository
2. Create feature branch
3. Add tests for new features
4. Submit pull request with description

## License

LGPL-3 (GNU Lesser General Public License v3.0)

See LICENSE file for full text.

## Credits

**Author:** Turkish POS Team  
**Maintainer:** Turkish POS Community  
**Contributors:** See CONTRIBUTORS file

## Changelog

### Version 19.0.1.0.0 (2024-01-01)
- Initial release for Odoo 19
- Abstract payment method model
- Concrete implementations (Cash, Card, Transfer)
- Modern `_processDirectFlow` integration
- 3D Secure flow
- Multi-currency support (TRY, USD, EUR)
- Turkish language support
- BIN detection and installments
- Dummy gateway for testing
- Comprehensive documentation

---

**Happy Payment Processing! 💳🇹🇷**
