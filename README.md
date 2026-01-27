# Turkish Virtual POS (Sanal POS) - Odoo 19

Custom Odoo 19 eCommerce payment module for Turkish banks with installment support, BIN detection, and 3D Secure.

## Features

- **4 Payment Gateways**: Param, Tosla, iyzico, QNBPay + 8 direct bank POS integrations
- **14 Turkish Banks**: Akbank, HalkBank, QNB Finans, Ziraat, Garanti, Is Bankasi, Yapi Kredi, Sekerbank, Denizbank, HSBC, TEB, ING, Vakifbank, Finansbank
- **BIN Detection**: Automatic card issuer identification from first 6 digits
- **Category-Based Installment Limits**: e.g. Furniture max 6 taksit, TV max 4
- **Installment Calculator**: Per-bank commission/interest rates, campaign support
- **3D Secure**: Full 3D Secure payment flow with bank redirect
- **Product Page Tab**: "Taksit Secenekleri" showing installment breakdown per bank
- **Checkout Integration**: Card form with live preview, dynamic installment options
- **Admin Panel**: Gateway config, bank management, BIN database, installment rules, category restrictions
- **No Core Overrides**: Clean custom module, fully compatible with stock Odoo 19

## Installation

1. Copy the `turkish_pos` folder to your Odoo addons path:
   ```bash
   cp -r turkish_pos /opt/odoo/addons/
   ```

2. Install Python dependencies:
   ```bash
   pip install requests zeep cryptography lxml
   ```

3. Restart Odoo and update the apps list:
   ```bash
   sudo systemctl restart odoo
   ```

4. In Odoo: **Apps** -> Search for "Turkish" -> Install **Turkish Virtual POS (Sanal POS)**

## Configuration

### 1. Gateway Setup (Saglayicilar)

Navigate to **Turkish POS > Yapilandirma > Saglayicilar**

- Each gateway has a **Kimlik Bilgileri** tab with JSON credentials
- Param test credentials are pre-filled:
  ```json
  {
    "clientCode": "10738",
    "username": "Test",
    "password": "Test",
    "guid": "0c13d406-873b-403b-9c09-a5766840d98c"
  }
  ```
- Set **Ortam** to "Test" for sandbox or "Uretim" for production

### 2. Bank Configuration (Bankalar)

Navigate to **Turkish POS > Yapilandirma > Bankalar**

- 14 banks are pre-configured with gateway mappings
- Each bank has:
  - **Taksit Ayarlari**: Installment counts with interest/commission rates
  - **Kategori Kisitlamalari**: Per-category max installment limits

### 3. Category Installment Limits

Navigate to **Turkish POS > Yapilandirma > Kategori Kisitlamalari**

To restrict installments for a product category:
1. Select the bank
2. Select the product category (e.g. "Mobilya" / Furniture)
3. Set **Maksimum Taksit** (e.g. 6 for furniture, 4 for TVs)
4. Optionally block specific installment counts

Example restrictions:
| Category | Max Installment |
|----------|----------------|
| Mobilya (Furniture) | 6 |
| Televizyon (TV) | 4 |
| Elektronik (Electronics) | 9 |

### 4. Payment Provider

Navigate to **Website > Configuration > Payment Providers**

- "Kredi Karti (Taksitli)" provider is auto-created
- Configure active banks, default bank for pesin payments, max installment, min amount

### 5. BIN Database

Navigate to **Turkish POS > Yapilandirma > BIN Numaralari**

- Pre-loaded BIN numbers for major Turkish bank cards
- Add new BINs as needed for card detection

## Adding New Categories

1. Go to **Turkish POS > Yapilandirma > Kategori Kisitlamalari**
2. Click **Create**
3. Select the bank and product category
4. Set the max installment limit
5. Repeat for each bank that needs the restriction

## Adding New Payment Gateways

1. Go to **Turkish POS > Yapilandirma > Saglayicilar**
2. Click **Create**
3. Fill in the gateway name, code, credentials (JSON), and payment model
4. Map banks to the gateway
5. Implement the integration class in `models/bank_integration.py`

## Module Structure

```
turkish_pos/
  __manifest__.py          # Module metadata and dependencies
  __init__.py              # Root imports
  models/
    payment_provider.py    # Extends payment.provider with turkish_pos code
    payment_transaction.py # Extends payment.transaction for 3D Secure
    turkish_pos_gateway.py # Gateway (Saglayici) model
    turkish_pos_bank.py    # Bank model with installment configs
    turkish_pos_bin.py     # BIN (Bank Identification Number) lookup
    turkish_pos_installment_config.py  # Per-bank installment rates
    turkish_pos_category_restriction.py # Category-based limits
    turkish_pos_transaction.py  # Transaction tracking & refunds
    bank_integration.py    # Gateway API integration classes
    product_template.py    # Product installment display data
    product_public_category.py  # Category installment settings
    sale_order.py          # Order installment tracking
  controllers/
    main.py                # API endpoints: installments, 3D return, validation
  views/
    gateway_views.xml      # Gateway admin views
    bank_views.xml         # Bank admin views
    payment_provider_views.xml  # Provider settings extension
    templates.xml          # Checkout card form + card preview
    dashboard_views.xml    # Menu structure
    ...
  templates/
    product_installments.xml  # Product page installment tab
    payment_3d.xml           # 3D Secure redirect/error/success pages
  static/src/
    js/payment_installments.js  # BIN detection + installment loading
    css/installment.css         # Installment UI styles
    css/payment_card.css        # Card preview styles
  data/
    gateway_data.xml       # Pre-configured gateways
    bank_data.xml          # 14 Turkish banks
    bin_data.xml           # Sample BIN numbers
    installment_data.xml   # Default installment configs
    provider_data.xml      # Default payment provider
  security/
    ir.model.access.csv    # Access control rules
```

## API Endpoints

| Endpoint | Type | Auth | Description |
|----------|------|------|-------------|
| `/turkish_pos/get_payment_installments` | JSON | Public | Get installment options for amount + BIN |
| `/turkish_pos/validate_bank_config` | JSON | User | Validate gateway credentials |
| `/payment/turkish_pos/return` | HTTP | Public | 3D Secure bank return callback |

## Dependencies

- Odoo 19 modules: `base`, `sale`, `payment`, `product`, `website_sale`, `web`
- Python: `requests`, `zeep`, `cryptography`, `lxml`

## License

LGPL-3
