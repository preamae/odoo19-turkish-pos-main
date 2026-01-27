/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

/**
 * TurkishPosPaymentForm
 *
 * Handles card input, BIN detection, installment loading, and
 * card preview updates on the payment form. Integrates with
 * the Turkish POS installment lookup endpoint.
 */
const TurkishPosPaymentForm = publicWidget.Widget.extend({
    selector: "#turkish_pos_payment_form",

    events: {
        "input #tp_card_number": "_onCardNumberInput",
        "input #tp_card_holder_name": "_onCardNameInput",
        "change #tp_expiry_month": "_onExpiryChange",
        "change #tp_expiry_year": "_onExpiryChange",
        "change .tp-installment-radio": "_onInstallmentChange",
    },

    /**
     * @override
     */
    start() {
        this._super(...arguments);
        this._lastBin = "";
        this._installmentsLoading = false;

        // Get amount from the order summary on the checkout page
        this._amount = this._getOrderAmount();
        this._currencySymbol = "TL";

        console.log("TurkishPosPaymentForm started, amount:", this._amount);

        return Promise.resolve();
    },

    // ------------------------------------------------------------------
    // Event handlers
    // ------------------------------------------------------------------

    /**
     * Handle card number input: format with spaces, detect BIN at 6 digits,
     * update card preview, and trigger installment loading.
     *
     * @param {Event} ev
     */
    _onCardNumberInput(ev) {
        const input = ev.currentTarget;
        let value = input.value.replace(/\D/g, "");

        // Limit to 19 digits (TROY cards can be up to 19)
        if (value.length > 19) {
            value = value.substring(0, 19);
        }

        // Format with spaces every 4 digits
        const formatted = value.replace(/(\d{4})(?=\d)/g, "$1 ");
        input.value = formatted;

        // Update card preview
        this._updateCardNumberPreview(value);

        // Detect card brand
        this._detectCardBrand(value);

        // BIN detection at 6+ digits
        if (value.length >= 6) {
            const bin = value.substring(0, 6);
            if (bin !== this._lastBin) {
                this._lastBin = bin;
                this._loadInstallments(bin);
            }
        } else {
            if (this._lastBin) {
                this._lastBin = "";
                this._hideInstallments();
            }
        }
    },

    /**
     * Handle card holder name input: update preview.
     *
     * @param {Event} ev
     */
    _onCardNameInput(ev) {
        const name = ev.currentTarget.value.trim();
        const previewEl = document.getElementById("tp_preview_card_holder");
        if (previewEl) {
            previewEl.textContent = name || "AD SOYAD";
        }
    },

    /**
     * Handle expiry month/year change: update preview.
     */
    _onExpiryChange() {
        const monthEl = document.getElementById("tp_expiry_month");
        const yearEl = document.getElementById("tp_expiry_year");
        const previewEl = document.getElementById("tp_preview_card_expiry");

        if (monthEl && yearEl && previewEl) {
            const month = monthEl.value || "AA";
            const year = yearEl.value || "YY";
            previewEl.textContent = month + "/" + (year.length > 2 ? year.substring(2) : year);
        }
    },

    /**
     * Handle installment radio selection: update hidden fields and total.
     *
     * @param {Event} ev
     */
    _onInstallmentChange(ev) {
        const radio = ev.currentTarget;
        const installmentCount = parseInt(radio.dataset.installmentCount, 10) || 1;
        const totalAmount = parseFloat(radio.dataset.totalAmount) || this._amount;
        const bankId = parseInt(radio.dataset.bankId, 10) || 0;

        // Update hidden fields
        const instField = document.getElementById("tp_selected_installment");
        const bankField = document.getElementById("tp_selected_bank_id");
        const totalField = document.getElementById("tp_total_amount");

        if (instField) instField.value = installmentCount;
        if (bankField) bankField.value = bankId;
        if (totalField) totalField.value = totalAmount.toFixed(2);
    },

    // ------------------------------------------------------------------
    // Installment loading
    // ------------------------------------------------------------------

    /**
     * Load installment options from the server for the given BIN.
     *
     * @param {string} bin - First 6 digits of the card number.
     */
    async _loadInstallments(bin) {
        if (this._installmentsLoading) {
            return;
        }
        this._installmentsLoading = true;

        const container = document.getElementById("tp_installment_container");
        const optionsEl = document.getElementById("tp_installment_options");
        const loadingEl = document.getElementById("tp_installment_loading");
        const errorEl = document.getElementById("tp_installment_error");

        // Show container and loading
        if (container) container.style.display = "block";
        if (loadingEl) loadingEl.style.display = "block";
        if (optionsEl) optionsEl.innerHTML = "";
        if (errorEl) errorEl.style.display = "none";

        try {
            console.log("TurkishPOS: Loading installments, amount:", this._amount, "bin:", bin);

            const response = await rpc("/turkish_pos/get_payment_installments", {
                amount: this._amount,
                bin_number: bin,
            });

            console.log("TurkishPOS: Installment response:", response);
            if (loadingEl) loadingEl.style.display = "none";

            if (response && response.success) {
                this._renderInstallments(response, optionsEl);
            } else {
                const errorMsg = (response && response.error) || "Taksit secenekleri yuklenemedi.";
                console.warn("TurkishPOS: Server returned error:", errorMsg);
                if (errorEl) {
                    errorEl.textContent = errorMsg;
                    errorEl.style.display = "block";
                }
            }
        } catch (error) {
            console.error("TurkishPOS: RPC error loading installments:", error);
            if (loadingEl) loadingEl.style.display = "none";
            if (errorEl) {
                errorEl.textContent = "Taksit secenekleri yuklenirken hata olustu.";
                errorEl.style.display = "block";
            }
        } finally {
            this._installmentsLoading = false;
        }
    },

    /**
     * Render installment options grouped by bank as radio list.
     *
     * @param {Object} response - Server response from get_payment_installments.
     * @param {HTMLElement} optionsEl - Container element for options.
     */
    _renderInstallments(response, optionsEl) {
        if (!optionsEl) return;

        const installments = response.installments || [];
        const amount = response.amount || this._amount;

        if (!installments.length) {
            optionsEl.innerHTML =
                '<div class="alert alert-info mb-0">' +
                '<i class="fa fa-info-circle me-1"></i>' +
                'Bu kart icin taksit secenegi bulunamamistir.' +
                '</div>';
            return;
        }

        let html = '';

        // Single payment option (always available)
        html += '<div class="tp-installment-group mb-3">';
        html += '<div class="form-check tp-installment-option">';
        html += '<input class="form-check-input tp-installment-radio" type="radio" ';
        html += 'name="tp_installment_selection" id="tp_inst_1" value="1" checked ';
        html += 'data-installment-count="1" ';
        html += 'data-total-amount="' + amount.toFixed(2) + '" ';
        html += 'data-bank-id="0">';
        html += '<label class="form-check-label w-100" for="tp_inst_1">';
        html += '<div class="d-flex justify-content-between align-items-center">';
        html += '<span class="fw-bold">Tek Cekim (Pesin)</span>';
        html += '<span class="fw-bold text-primary">' + this._formatCurrency(amount) + '</span>';
        html += '</div>';
        html += '</label>';
        html += '</div>';
        html += '</div>';

        // Bank-grouped installment options
        for (const bankData of installments) {
            const bank = bankData.bank || {};
            const bankInstallments = bankData.installments || [];

            if (!bankInstallments.length) continue;

            html += '<div class="tp-installment-group mb-3">';
            html += '<div class="tp-bank-header d-flex align-items-center mb-2 pb-1 border-bottom">';
            html += '<i class="fa fa-university me-2 text-muted"></i>';
            html += '<span class="fw-bold">' + this._escapeHtml(bank.name || '') + '</span>';
            if (bank.code) {
                html += '<span class="badge bg-light text-muted ms-2 small">' + this._escapeHtml(bank.code) + '</span>';
            }
            html += '</div>';

            for (const inst of bankInstallments) {
                if (inst.installment_count <= 1) continue; // skip single payment (already shown above)

                const radioId = 'tp_inst_' + bank.id + '_' + inst.installment_count;

                html += '<div class="form-check tp-installment-option">';
                html += '<input class="form-check-input tp-installment-radio" type="radio" ';
                html += 'name="tp_installment_selection" ';
                html += 'id="' + radioId + '" ';
                html += 'value="' + inst.installment_count + '" ';
                html += 'data-installment-count="' + inst.installment_count + '" ';
                html += 'data-total-amount="' + inst.total_amount.toFixed(2) + '" ';
                html += 'data-bank-id="' + bank.id + '">';
                html += '<label class="form-check-label w-100" for="' + radioId + '">';
                html += '<div class="d-flex justify-content-between align-items-center">';
                html += '<div>';
                html += '<span>' + inst.installment_count + ' Taksit</span>';
                if (inst.is_campaign) {
                    html += ' <span class="badge bg-danger ms-1">Kampanya</span>';
                }
                if (inst.interest_rate === 0) {
                    html += ' <span class="badge bg-success ms-1">Faizsiz</span>';
                }
                html += '</div>';
                html += '<div class="text-end">';
                html += '<div class="fw-bold">' + this._formatCurrency(inst.installment_amount) + '<small class="text-muted">/ay</small></div>';
                html += '<small class="text-muted">Toplam: ' + this._formatCurrency(inst.total_amount) + '</small>';
                if (inst.interest_rate > 0) {
                    html += '<br><small class="text-muted">Faiz: %' + inst.interest_rate.toFixed(2) + '</small>';
                }
                html += '</div>';
                html += '</div>';
                html += '</label>';
                html += '</div>';
            }

            html += '</div>';
        }

        optionsEl.innerHTML = html;

        // Reset hidden fields to single payment
        const instField = document.getElementById("tp_selected_installment");
        const bankField = document.getElementById("tp_selected_bank_id");
        if (instField) instField.value = 1;
        if (bankField) bankField.value = 0;
    },

    /**
     * Hide installment container.
     */
    _hideInstallments() {
        const container = document.getElementById("tp_installment_container");
        if (container) container.style.display = "none";

        const instField = document.getElementById("tp_selected_installment");
        const bankField = document.getElementById("tp_selected_bank_id");
        if (instField) instField.value = 1;
        if (bankField) bankField.value = 0;
    },

    // ------------------------------------------------------------------
    // Display updates
    // ------------------------------------------------------------------

    /**
     * Update the card number preview on the card visual.
     *
     * @param {string} digits - Raw digits of the card number.
     */
    _updateCardNumberPreview(digits) {
        const previewEl = document.getElementById("tp_preview_card_number");
        if (!previewEl) return;

        if (!digits) {
            previewEl.textContent = "**** **** **** ****";
            return;
        }

        // Pad to at least 16, support up to 19
        const padded = digits.padEnd(16, "*");
        let display =
            padded.substring(0, 4) + " " +
            padded.substring(4, 8) + " " +
            padded.substring(8, 12) + " " +
            padded.substring(12, 16);

        // Show extra digits for 17-19 digit cards (TROY)
        if (digits.length > 16) {
            display += " " + digits.substring(16);
        }

        previewEl.textContent = display;
    },

    /**
     * Detect the card brand based on the number prefix (Visa, Mastercard, Troy).
     *
     * @param {string} digits - Raw digits of the card number.
     */
    _detectCardBrand(digits) {
        const brandEl = document.getElementById("tp_preview_card_brand");
        const hiddenType = document.getElementById("tp_card_type");
        const cvvInput = document.getElementById("tp_cvv");

        let brand = "";
        let brandName = "";
        let cvvLength = 3;

        if (/^4/.test(digits)) {
            brand = "visa";
            brandName = "VISA";
        } else if (/^5[1-5]/.test(digits) || /^2[2-7]/.test(digits)) {
            brand = "mastercard";
            brandName = "MASTERCARD";
        } else if (/^9792/.test(digits) || /^65/.test(digits)) {
            brand = "troy";
            brandName = "TROY";
        } else if (/^3[47]/.test(digits)) {
            brand = "amex";
            brandName = "AMEX";
            cvvLength = 4;
        }

        if (brandEl) {
            // Show brand logo SVG or text
            if (brand === "visa") {
                brandEl.innerHTML = '<svg viewBox="0 0 48 16" width="48" height="16"><text x="0" y="13" fill="#1A1F71" font-size="14" font-weight="bold" font-family="Arial">VISA</text></svg>';
            } else if (brand === "mastercard") {
                brandEl.innerHTML = '<svg viewBox="0 0 40 24" width="40" height="24"><circle cx="14" cy="12" r="10" fill="#EB001B" opacity="0.8"/><circle cx="26" cy="12" r="10" fill="#F79E1B" opacity="0.8"/></svg>';
            } else if (brand === "troy") {
                brandEl.innerHTML = '<span style="color:#004B87;font-weight:bold;font-size:12px;">TROY</span>';
            } else if (brand === "amex") {
                brandEl.innerHTML = '<span style="color:#2E77BC;font-weight:bold;font-size:11px;">AMEX</span>';
            } else {
                brandEl.innerHTML = '';
            }
        }
        if (hiddenType) hiddenType.value = brand;

        // Update CVV max length based on card brand
        if (cvvInput) {
            cvvInput.maxLength = cvvLength;
            cvvInput.placeholder = cvvLength === 4 ? "****" : "***";
        }
    },

    /**
     * Extract order amount from the checkout page.
     */
    _getOrderAmount() {
        // Try to find the total from the order summary
        // Odoo 19 selectors for the checkout order total
        const selectors = [
            ".oe_order_total .oe_currency_value",
            ".o_total .oe_currency_value",
            "#order_total .oe_currency_value",
            "[data-oe-expression*='amount_total'] .oe_currency_value",
            ".o_wsale_order_summary .oe_currency_value:last-child",
        ];

        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el) {
                const parsed = this._parseTurkishAmount(el.textContent);
                if (parsed > 0) {
                    console.log("TurkishPOS: Amount found via", sel, "=", parsed);
                    return parsed;
                }
            }
        }

        // Fallback: find any element with data-tp-amount attribute
        const amountEl = document.querySelector("[data-tp-amount]");
        if (amountEl) {
            return parseFloat(amountEl.dataset.tpAmount) || 0;
        }

        // Fallback: try the hidden amount field
        const hiddenAmount = document.querySelector("input[name='amount']");
        if (hiddenAmount) {
            return parseFloat(hiddenAmount.value) || 0;
        }

        // Last fallback: find any Toplam value on the page
        const allValues = document.querySelectorAll(".oe_currency_value");
        if (allValues.length > 0) {
            // Use the last one (usually the grand total)
            const lastVal = allValues[allValues.length - 1];
            const parsed = this._parseTurkishAmount(lastVal.textContent);
            if (parsed > 0) {
                console.log("TurkishPOS: Amount from last currency value =", parsed);
                return parsed;
            }
        }

        console.warn("TurkishPOS: Could not find order amount on page");
        return 0;
    },

    /**
     * Parse a Turkish formatted amount string to a float.
     * Turkish format: 1.000,50 (dot = thousands, comma = decimal)
     * Also handles: 1000.50 (standard format), 1000, 1.000
     *
     * @param {string} text - The amount text to parse.
     * @returns {number} Parsed amount or 0.
     */
    _parseTurkishAmount(text) {
        if (!text) return 0;

        // Strip non-numeric chars except dots and commas
        let cleaned = text.replace(/[^\d.,]/g, "").trim();
        if (!cleaned) return 0;

        // Detect Turkish format: if there's a comma AND dots before it,
        // the dots are thousands separators
        // Examples: "1.000,50" -> 1000.50, "1.200.000,00" -> 1200000.00
        if (cleaned.includes(",")) {
            // Remove dots (thousands separators), replace comma with dot (decimal)
            cleaned = cleaned.replace(/\./g, "").replace(",", ".");
        }
        // If no comma, dots might be decimal (standard format: "1000.50")
        // or thousands ("1.000") - if dot is followed by exactly 3 digits at end, it's thousands
        else if (cleaned.includes(".")) {
            const parts = cleaned.split(".");
            if (parts.length === 2 && parts[1].length === 3) {
                // Likely thousands separator: "1.000" -> 1000
                cleaned = cleaned.replace(/\./g, "");
            }
            // Otherwise keep as-is (decimal point): "1000.50" -> 1000.50
        }

        const result = parseFloat(cleaned);
        return isNaN(result) ? 0 : result;
    },

    // ------------------------------------------------------------------
    // Utility methods
    // ------------------------------------------------------------------

    /**
     * Format a number as currency with the configured symbol.
     *
     * @param {number} value - The amount to format.
     * @returns {string} Formatted currency string.
     */
    _formatCurrency(value) {
        const formatted = value.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
        return formatted + " " + this._currencySymbol;
    },

    /**
     * Escape HTML entities in a string to prevent XSS.
     *
     * @param {string} text - The text to escape.
     * @returns {string} Escaped string.
     */
    _escapeHtml(text) {
        const div = document.createElement("div");
        div.appendChild(document.createTextNode(text));
        return div.innerHTML;
    },
});

publicWidget.registry.TurkishPosPaymentForm = TurkishPosPaymentForm;

export default TurkishPosPaymentForm;
