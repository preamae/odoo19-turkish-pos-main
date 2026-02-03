# Turkish POS Abstract Payment - Installation & Quick Start

## Quick Installation Guide

### 1. Prerequisites Check
```bash
# Check Odoo version
odoo-bin --version  # Should be 19.0 or higher

# Check Python version
python3 --version  # Should be 3.10 or higher

# IMPORTANT: Ensure Turkish POS module is installed
# This module depends on turkish_pos and must be installed first
```

### 2. Install Turkish POS Module (if not already installed)

The `turkish_pos` module must be installed before installing this module.

```bash
# Verify turkish_pos is in your addons path
ls /opt/odoo/addons/turkish_pos

# If not present, install it first via Odoo Apps interface
# or copy it to the addons directory
```

### 3. Install Abstract Payment Module

#### Option A: Manual Installation
```bash
# Navigate to Odoo addons directory
cd /opt/odoo/addons

# Copy the module
cp -r /path/to/turkish_pos_abstract_payment .

# Set proper permissions
sudo chown -R odoo:odoo turkish_pos_abstract_payment
sudo chmod -R 755 turkish_pos_abstract_payment

# Restart Odoo
sudo systemctl restart odoo
```

#### Option B: Docker Installation
```bash
# Add to your docker-compose.yml volumes:
volumes:
  - ./turkish_pos_abstract_payment:/mnt/extra-addons/turkish_pos_abstract_payment

# Restart container
docker-compose restart web
```

### 3. Activate Module in Odoo

1. Log in as administrator
2. Go to **Apps** menu
3. Click **Update Apps List**
4. Remove "Apps" filter in search
5. Search: "Turkish POS Abstract Payment"
6. Click **Activate** or **Install**

### 4. Verify Installation

After installation, check these menus exist:
- **Abstract Payment** (top menu)
  - **Payment Methods**
  - **Payment Gateways**

You should see 3 default payment methods:
1. Nakit Ödeme (Cash)
2. Kredi Kartı (Credit Card)
3. Banka Havalesi / EFT (Bank Transfer)

## Quick Test

### Test Payment Form

1. Navigate to: `http://your-odoo-site.com/payment/abstract/test`
2. Select "Kredi Kartı" (Credit Card)
3. Enter test card: `4111 1111 1111 1111`
4. CVV: `123`
5. Expiry: `12/2025`
6. Click "Ödemeyi Tamamla"
7. On 3D Secure page, click "Ödemeyi Onayla"
8. You should see success page

### Test API Endpoints

```bash
# Get payment methods
curl -X POST http://localhost:8069/payment/abstract/methods \
  -H "Content-Type: application/json" \
  -d '{"amount": 100}'

# Get installments
curl -X POST http://localhost:8069/payment/abstract/installments \
  -H "Content-Type: application/json" \
  -d '{
    "method_id": 2,
    "amount": 1000,
    "bin_number": "542119"
  }'
```

## Configuration Checklist

- [ ] Module installed and activated
- [ ] Payment methods visible in menu
- [ ] Gateway configured (Dummy Gateway active)
- [ ] Currencies active (TRY, USD, EUR)
- [ ] Test payment page accessible
- [ ] Card payment works with test data
- [ ] 3D Secure flow completes
- [ ] Turkish translations showing

## Common First-Time Issues

### Issue: "Module not found"
**Solution:**
```bash
# Check module is in addons path
ls -la /opt/odoo/addons/turkish_pos_abstract_payment

# Check Odoo configuration
cat /etc/odoo/odoo.conf | grep addons_path
```

### Issue: "Access Rights Error"
**Solution:**
```bash
# Update module with security rules
odoo-bin -c odoo.conf -u turkish_pos_abstract_payment --stop-after-init
```

### Issue: "Templates not loading"
**Solution:**
```bash
# Clear assets and restart
rm -rf /var/lib/odoo/sessions/*
sudo systemctl restart odoo
```

## Next Steps

1. **Configure Production Gateway:**
   - Go to: **Abstract Payment > Payment Gateways**
   - Create new gateway with real credentials
   - Set environment to "Production"

2. **Customize Payment Methods:**
   - Edit existing methods or create new ones
   - Set appropriate amount limits
   - Configure installment options

3. **Integrate with Website:**
   - Add payment form to checkout page
   - Configure website_sale integration
   - Test complete purchase flow

4. **Monitor Transactions:**
   - Check Odoo logs for payment activity
   - Review payment.transaction records
   - Set up error notifications

## Support Resources

- **Module README:** `README.md` - Full documentation
- **Code Documentation:** Inline docstrings in all files
- **Test Page:** `/payment/abstract/test`
- **GitHub Issues:** Report bugs and feature requests

## License

LGPL-3 - See LICENSE file

---

**Installation Complete! 🎉**

Proceed to full README.md for detailed usage and API documentation.
