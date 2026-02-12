# Fix Summary: Many2many Table Conflict Error

## Problem

The module `turkish_pos_abstract_payment` failed to install with the following error:

```
TypeError: Many2many fields payment.method.cash.turkish_pos_bank_ids and 
payment.method.turkish_pos_bank_ids use the same table and columns
```

**Error Location:** During Odoo model loading, when setting up Many2many field relations

## Root Cause Analysis

The issue was caused by model inheritance conflicts in `test_payment_methods.py`:

### What Happened

1. **Base Model:** `payment.method` has a Many2many field:
   ```python
   turkish_pos_bank_ids = fields.Many2many(
       comodel_name='turkish.pos.bank',
       relation='payment_method_turkish_pos_bank_rel',  # ← Table name
       column1='method_id',
       column2='bank_id',
       ...
   )
   ```

2. **Child Models:** Three models inherited from `payment.method`:
   - `payment.method.cash`
   - `payment.method.credit.card`
   - `payment.method.bank.transfer`

3. **The Problem:** When child models inherit from a parent:
   - They inherit ALL fields from the parent
   - Including the `turkish_pos_bank_ids` Many2many field
   - All children tried to use the SAME relation table
   - Odoo detected the conflict and raised TypeError

### Why This Is a Problem

In Odoo, each Many2many field needs a unique combination of:
- Relation table name
- Column names

When multiple models try to use identical relation parameters, it creates a database conflict.

### Why These Models Existed

These model classes were created as **examples/demos** to show how payment methods could be extended. However:
- They were never actually needed
- The data file already creates payment method records directly
- They only caused conflicts without adding value

## Solution

**Removed the conflicting model classes entirely.**

### Changes Made

#### 1. `models/test_payment_methods.py`

**Before:**
```python
class PaymentMethodCash(models.Model):
    _name = 'payment.method.cash'
    _inherit = 'payment.method'
    # ... inherited turkish_pos_bank_ids field

class PaymentMethodCreditCard(models.Model):
    _name = 'payment.method.credit.card'
    _inherit = 'payment.method'
    # ... inherited turkish_pos_bank_ids field

class PaymentMethodBankTransfer(models.Model):
    _name = 'payment.method.bank.transfer'
    _inherit = 'payment.method'
    # ... inherited turkish_pos_bank_ids field
```

**After:**
```python
# Removed all model classes
# Added comprehensive documentation explaining:
# - Why they were removed
# - How to create payment methods correctly
# - Kept helper function for reference
```

#### 2. `security/ir.model.access.csv`

**Removed:**
- `access_payment_method_cash_admin`
- `access_payment_method_credit_card_admin`
- `access_payment_method_bank_transfer_admin`

**Kept:**
- Access rules for `payment.method`
- Access rules for `payment.gateway`

## How Payment Methods Work Now

Payment methods are created as **records** of the `payment.method` model, not as separate model classes.

### Method 1: Via Data Files (Recommended)

In `data/abstract_payment_data.xml`:

```xml
<record id="payment_method_cash" model="payment.method">
    <field name="name">Nakit Ödeme</field>
    <field name="code">cash</field>
    <field name="payment_type">cash</field>
    <field name="supports_installments" eval="False"/>
    ...
</record>
```

### Method 2: Via Python Code

```python
cash_method = env['payment.method'].create({
    'name': 'Cash Payment',
    'code': 'cash',
    'payment_type': 'cash',
    'supports_installments': False,
    ...
})
```

### Method 3: Via Odoo UI

1. Navigate to: **Abstract Payment > Payment Methods**
2. Click **Create**
3. Fill in the form
4. Save

## Verification

After this fix:

1. ✅ Module installs successfully without errors
2. ✅ No Many2many table conflicts
3. ✅ Payment methods work correctly as records
4. ✅ Three default payment methods created:
   - Nakit Ödeme (Cash)
   - Kredi Kartı (Credit Card)
   - Banka Havalesi / EFT (Bank Transfer)

## Testing

To verify the fix works:

```bash
# In Odoo
1. Go to Apps menu
2. Update Apps List
3. Search for "Turkish POS Abstract Payment"
4. Click Install
5. Should install successfully without errors

# Verify payment methods
6. Go to: Abstract Payment > Payment Methods
7. Should see 3 payment methods created
8. All should be instances of payment.method model
```

## Impact

- **Breaking Change:** No
- **Data Loss:** No
- **Backward Compatible:** Yes
- **User Action Required:** Just reinstall/update the module
- **Functional Changes:** None - payment methods work the same way

## Technical Details

### Odoo Model Inheritance Types

Odoo has two main inheritance types:

1. **`_inherit`** (Classical inheritance)
   - Extends existing model
   - Inherits all fields and methods
   - Same database table
   - **Issue:** Child inherits parent's Many2many fields with same table

2. **`_inherits`** (Delegation inheritance)
   - Creates separate table
   - Links to parent via Many2one
   - Different approach, not applicable here

### Why Separate Models Don't Work Here

Creating separate models like `payment.method.cash` doesn't make sense because:

1. **Polymorphism via Records:** Odoo's design pattern is to use records with different field values, not separate model classes
2. **Field Inheritance:** Child models inherit ALL parent fields, including Many2many relations
3. **No Specialization Needed:** Payment type differences are handled by the `payment_type` field

### The Right Pattern

```python
# ❌ WRONG: Separate model classes
class PaymentMethodCash(models.Model):
    _name = 'payment.method.cash'
    _inherit = 'payment.method'

# ✅ RIGHT: Records with different configurations
cash = env['payment.method'].create({
    'code': 'cash',
    'payment_type': 'cash',
    ...
})

card = env['payment.method'].create({
    'code': 'card',
    'payment_type': 'card',
    ...
})
```

## Related Documentation

- See `models/test_payment_methods.py` for detailed documentation
- See `data/abstract_payment_data.xml` for example data records
- See `README.md` for usage instructions

## Status

✅ **FIXED** - Module now installs correctly without Many2many conflicts.

---

*Fix Date: 2026-02-03*  
*Commit: 0197cad*  
*Fixed by: Removing conflicting test model classes*
