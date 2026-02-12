# Fix Summary: Module Installation Error

## Problem

The module `turkish_pos_abstract_payment` failed to install with the following error:

```
AssertionError: Field payment.method.turkish_pos_bank_ids with unknown comodel_name 'turkish.pos.bank'
```

**Error Location:** During Odoo module loading, specifically in the field setup phase (`fields_relational.py:1260`)

## Root Cause Analysis

The `turkish_pos_abstract_payment` module's `payment_method.py` file contains a Many2many field:

```python
turkish_pos_bank_ids = fields.Many2many(
    comodel_name='turkish.pos.bank',
    relation='payment_method_turkish_pos_bank_rel',
    column1='method_id',
    column2='bank_id',
    string='Turkish POS Banks',
    help='Turkish banks available for this payment method'
)
```

This field references the `turkish.pos.bank` model, which is defined in the parent `turkish_pos` module. However, the `__manifest__.py` file did not declare `turkish_pos` as a dependency, causing Odoo to attempt loading `turkish_pos_abstract_payment` before `turkish_pos`, resulting in the referenced model not being available.

## Solution

Added `'turkish_pos'` to the module dependencies in `__manifest__.py`:

```python
'depends': [
    'base',
    'payment',
    'website_sale',
    'product',
    'sale',
    'web',
    'turkish_pos',  # Required for turkish.pos.bank and turkish.pos.bin models
],
```

## Changes Made

1. **turkish_pos_abstract_payment/__manifest__.py**
   - Added `'turkish_pos'` to the `depends` list
   - Added comment explaining the dependency

2. **turkish_pos_abstract_payment/README.md**
   - Updated Prerequisites section to list `turkish_pos` as required
   - Updated Installation steps to mention installing `turkish_pos` first

3. **turkish_pos_abstract_payment/INSTALL.md**
   - Added prerequisite check for `turkish_pos` module
   - Added step to install Turkish POS module before abstract payment

4. **turkish_pos_abstract_payment/MODULE_SUMMARY.md**
   - Added dependencies to module information section

5. **IMPLEMENTATION_COMPLETE.md**
   - Added note about installing `turkish_pos` first

## Verification

After this fix:
1. Odoo will load `turkish_pos` module first
2. The `turkish.pos.bank` and `turkish.pos.bin` models will be available
3. `turkish_pos_abstract_payment` module will load successfully
4. All Many2many relationships will resolve correctly

## Installation Order

**Correct installation order:**
1. Install `turkish_pos` module (parent module)
2. Install `turkish_pos_abstract_payment` module

## Impact

- **Breaking Change:** No
- **Backward Compatible:** Yes (assumes turkish_pos is already installed)
- **Database Migration Required:** No
- **User Action Required:** Ensure turkish_pos is installed before this module

## Testing

To verify the fix works:

```bash
# In Odoo
1. Go to Apps menu
2. Update Apps List
3. Search for "Turkish POS Abstract Payment"
4. Click Install
5. Should install successfully without errors
```

## Related Models

The following models from `turkish_pos` are used by `turkish_pos_abstract_payment`:
- `turkish.pos.bank` - Bank configuration and installment options
- `turkish.pos.bin` - BIN number to bank mapping

## Status

✅ **FIXED** - Module now declares proper dependencies and will install correctly.

---

*Fix Date: 2026-02-03*
*Fixed in Commit: 555986a*
