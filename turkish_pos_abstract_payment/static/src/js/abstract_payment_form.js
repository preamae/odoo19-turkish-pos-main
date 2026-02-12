/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

/**
 * AbstractPaymentForm Widget
 * 
 * Modern Odoo 19 payment form with:
 * - Null-guarded element access
 * - _processDirectFlow integration
 * - BIN-based installment detection
 * - 3D Secure flow support
 * - Multi-currency support (TRY, USD, EUR)
 * - Turkish language validation messages
 */
const AbstractPaymentForm = publicWidget.Widget.extend({
    selector: "#abstract_payment_form",
    
    events: {
        "input #card_number": "_onCardNumberInput",
        "input #card_holder_name": "_onCardHolderInput",
        "change #expiry_month": "_onExpiryChange",
        "change #expiry_year": "_onExpiryChange",
        "input #cvv": "_onCvvInput",
        "change .installment-radio": "_onInstallmentChange",
        "change #payment_method": "_onPaymentMethodChange",
        "submit": "_onFormSubmit",
    },
    
    /**
     * @override
     */
    start() {
        this._super(...arguments);
        
        // Initialize state - null-guarded
        this._lastBin = "";
        this._installmentsLoading = false;
        this._selectedInstallment = 1;
        this._currentMethodId = null;
        
        // Get form data
        this._amount = this._getAmount();
        this._currencyId = this._getCurrencyId();
        this._reference = this._generateReference();
        
        console.log("AbstractPaymentForm initialized:", {
            amount: this._amount,
            currencyId: this._currencyId,
            reference: this._reference
        });
        
        // Load payment methods
        this._loadPaymentMethods();
        
        return Promise.resolve();
    },
    
    // ========================================================================
    // EVENT HANDLERS
    // ========================================================================
    
    /**
     * Handle card number input with BIN detection and formatting.
     * Null-guarded to prevent "Cannot read properties of null" errors.
     */
    _onCardNumberInput(ev) {
        const input = ev.currentTarget;
        if (!input) {
            console.warn("Card number input element is null");
            return;
        }
        
        let value = input.value.replace(/\D/g, "");
        
        // Limit to 19 digits (TROY cards can be up to 19)
        if (value.length > 19) {
            value = value.substring(0, 19);
        }
        
        // Format with spaces every 4 digits
        const formatted = value.replace(/(\d{4})(?=\d)/g, "$1 ");
        input.value = formatted;
        
        // Update card preview (null-guarded)
        this._updateCardPreview("number", value);
        
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
                this._clearInstallments();
            }
        }
    },
    
    /**
     * Handle cardholder name input.
     */
    _onCardHolderInput(ev) {
        const input = ev.currentTarget;
        if (!input) return;
        
        // Convert to uppercase
        input.value = input.value.toUpperCase();
        
        // Update card preview
        this._updateCardPreview("holder", input.value);
    },
    
    /**
     * Handle expiry date changes.
     */
    _onExpiryChange(ev) {
        const monthSelect = this.el?.querySelector("#expiry_month");
        const yearSelect = this.el?.querySelector("#expiry_year");
        
        if (monthSelect && yearSelect) {
            const month = monthSelect.value;
            const year = yearSelect.value;
            
            if (month && year) {
                this._updateCardPreview("expiry", `${month}/${year.slice(-2)}`);
            }
        }
    },
    
    /**
     * Handle CVV input.
     */
    _onCvvInput(ev) {
        const input = ev.currentTarget;
        if (!input) return;
        
        // Only allow digits, max 4
        let value = input.value.replace(/\D/g, "");
        if (value.length > 4) {
            value = value.substring(0, 4);
        }
        input.value = value;
    },
    
    /**
     * Handle installment selection change.
     */
    _onInstallmentChange(ev) {
        const radio = ev.currentTarget;
        if (!radio) return;
        
        this._selectedInstallment = parseInt(radio.value) || 1;
        console.log("Selected installment:", this._selectedInstallment);
    },
    
    /**
     * Handle payment method change.
     */
    _onPaymentMethodChange(ev) {
        const select = ev.currentTarget;
        if (!select) return;
        
        this._currentMethodId = parseInt(select.value);
        console.log("Selected payment method:", this._currentMethodId);
        
        // Show/hide card form based on method type
        this._toggleCardForm();
        
        // Clear previous installments
        this._clearInstallments();
        this._lastBin = "";
    },
    
    /**
     * Handle form submission with validation and _processDirectFlow.
     */
    async _onFormSubmit(ev) {
        ev.preventDefault();
        
        const form = ev.currentTarget;
        if (!form) return;
        
        // Disable submit button to prevent double submission
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = "İşleniyor...";
        }
        
        try {
            // Validate form
            const validation = await this._validateForm();
            if (!validation.valid) {
                this._showErrors(validation.errors);
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = "Ödemeyi Tamamla";
                }
                return;
            }
            
            // Process payment using Odoo 16+ _processDirectFlow logic
            await this._processDirectFlow();
            
        } catch (error) {
            console.error("Payment submission error:", error);
            this._showError("Ödeme işlemi sırasında bir hata oluştu: " + error.message);
            
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = "Ödemeyi Tamamla";
            }
        }
    },
    
    // ========================================================================
    // PAYMENT PROCESSING - Modern Odoo 19 _processDirectFlow
    // ========================================================================
    
    /**
     * Process direct payment flow (Odoo 16+ style).
     * 
     * This method implements the modern Odoo payment flow:
     * 1. Initiate payment
     * 2. If 3D Secure required, redirect to 3D page
     * 3. Return from 3D, complete payment
     * 4. Update transaction status
     */
    async _processDirectFlow() {
        console.log("Starting _processDirectFlow...");
        
        try {
            // Get payment data
            const paymentData = this._getPaymentData();
            
            // Initiate payment
            const initiateResult = await rpc("/payment/abstract/initiate", {
                method_id: this._currentMethodId,
                amount: this._amount,
                currency_id: this._currencyId,
                reference: this._reference,
                card_data: paymentData.card_data,
                installments: this._selectedInstallment,
            });
            
            if (!initiateResult.success) {
                throw new Error(initiateResult.error || "Ödeme başlatılamadı");
            }
            
            console.log("Payment initiated:", initiateResult);
            
            // Handle 3D Secure redirect if required
            if (initiateResult.requires_3d) {
                this._handle3DSecure(initiateResult);
            } else {
                // Direct payment completed
                this._handlePaymentSuccess(initiateResult);
            }
            
        } catch (error) {
            console.error("_processDirectFlow error:", error);
            throw error;
        }
    },
    
    /**
     * Handle 3D Secure redirect flow.
     */
    _handle3DSecure(result) {
        console.log("Redirecting to 3D Secure...");
        
        if (result.redirect_form_html) {
            // Create and submit form for 3D Secure redirect
            const formContainer = document.createElement("div");
            formContainer.innerHTML = result.redirect_form_html;
            document.body.appendChild(formContainer);
            
            const form = formContainer.querySelector("form");
            if (form) {
                form.submit();
            }
        } else if (result.redirect_url) {
            // Direct redirect
            window.location.href = result.redirect_url;
        } else {
            this._showError("3D Secure yönlendirme bilgisi bulunamadı");
        }
    },
    
    /**
     * Handle successful payment completion.
     */
    _handlePaymentSuccess(result) {
        console.log("Payment successful:", result);
        
        // Show success message
        this._showSuccess(result.message || "Ödeme başarıyla tamamlandı!");
        
        // Redirect to success page after a short delay
        setTimeout(() => {
            window.location.href = "/shop/payment/validate";
        }, 2000);
    },
    
    // ========================================================================
    // DATA LOADING
    // ========================================================================
    
    /**
     * Load available payment methods.
     */
    async _loadPaymentMethods() {
        try {
            const result = await rpc("/payment/abstract/methods", {
                amount: this._amount,
                currency_id: this._currencyId,
            });
            
            if (result.success && result.methods) {
                this._renderPaymentMethods(result.methods);
            }
        } catch (error) {
            console.error("Error loading payment methods:", error);
        }
    },
    
    /**
     * Load installment options based on BIN.
     */
    async _loadInstallments(binNumber) {
        if (this._installmentsLoading || !this._currentMethodId) {
            return;
        }
        
        this._installmentsLoading = true;
        this._showInstallmentsLoading();
        
        try {
            const result = await rpc("/payment/abstract/installments", {
                method_id: this._currentMethodId,
                amount: this._amount,
                currency_id: this._currencyId,
                bin_number: binNumber,
            });
            
            if (result.success && result.installments) {
                this._renderInstallments(result.installments);
            } else {
                this._clearInstallments();
            }
        } catch (error) {
            console.error("Error loading installments:", error);
            this._clearInstallments();
        } finally {
            this._installmentsLoading = false;
        }
    },
    
    // ========================================================================
    // VALIDATION
    // ========================================================================
    
    /**
     * Validate payment form with Turkish error messages.
     */
    async _validateForm() {
        const errors = [];
        
        // Validate payment method selection
        if (!this._currentMethodId) {
            errors.push("Lütfen bir ödeme yöntemi seçin");
        }
        
        // Get method type
        const methodSelect = this.el?.querySelector("#payment_method");
        const selectedOption = methodSelect?.options[methodSelect.selectedIndex];
        const paymentType = selectedOption?.dataset?.paymentType;
        
        // Card-specific validation
        if (paymentType === "card") {
            const cardErrors = this._validateCardData();
            errors.push(...cardErrors);
        }
        
        // Server-side validation
        if (errors.length === 0 && this._currentMethodId) {
            try {
                const result = await rpc("/payment/abstract/validate", {
                    method_id: this._currentMethodId,
                    amount: this._amount,
                    currency_id: this._currencyId,
                    card_data: this._getCardData(),
                });
                
                if (result.success && !result.valid) {
                    errors.push(...result.errors);
                }
            } catch (error) {
                console.error("Validation error:", error);
                errors.push("Doğrulama hatası: " + error.message);
            }
        }
        
        return {
            valid: errors.length === 0,
            errors: errors,
        };
    },
    
    /**
     * Validate card data fields.
     */
    _validateCardData() {
        const errors = [];
        
        const cardNumber = this.el?.querySelector("#card_number")?.value.replace(/\D/g, "") || "";
        const cardHolder = this.el?.querySelector("#card_holder_name")?.value || "";
        const expiryMonth = this.el?.querySelector("#expiry_month")?.value || "";
        const expiryYear = this.el?.querySelector("#expiry_year")?.value || "";
        const cvv = this.el?.querySelector("#cvv")?.value || "";
        
        // Card number
        if (!cardNumber) {
            errors.push("Kart numarası gerekli");
        } else if (cardNumber.length < 13 || cardNumber.length > 19) {
            errors.push("Kart numarası 13-19 rakam olmalıdır");
        }
        
        // Cardholder name
        if (!cardHolder || cardHolder.trim().length < 3) {
            errors.push("Kart sahibi adı gerekli (en az 3 karakter)");
        }
        
        // Expiry date
        if (!expiryMonth) {
            errors.push("Son kullanma ayı gerekli");
        }
        if (!expiryYear) {
            errors.push("Son kullanma yılı gerekli");
        }
        
        // CVV
        if (!cvv) {
            errors.push("CVV gerekli");
        } else if (cvv.length < 3 || cvv.length > 4) {
            errors.push("CVV 3-4 rakam olmalıdır");
        }
        
        return errors;
    },
    
    // ========================================================================
    // UI UPDATES
    // ========================================================================
    
    /**
     * Render payment methods dropdown.
     */
    _renderPaymentMethods(methods) {
        const select = this.el?.querySelector("#payment_method");
        if (!select) return;
        
        // Clear existing options
        select.innerHTML = '<option value="">Ödeme yöntemi seçin...</option>';
        
        // Add method options
        methods.forEach(method => {
            const option = document.createElement("option");
            option.value = method.id;
            option.textContent = method.name;
            option.dataset.paymentType = method.payment_type;
            option.dataset.supportsInstallments = method.supports_installments;
            select.appendChild(option);
        });
    },
    
    /**
     * Render installment options.
     */
    _renderInstallments(installments) {
        const container = this.el?.querySelector("#installments_container");
        if (!container) return;
        
        container.innerHTML = "";
        
        if (!installments || installments.length === 0) {
            container.innerHTML = '<p class="text-muted">Taksit seçeneği mevcut değil</p>';
            return;
        }
        
        // Render installment options per bank
        installments.forEach(bankData => {
            const bankSection = document.createElement("div");
            bankSection.className = "bank-installments mb-3";
            
            const bankTitle = document.createElement("h6");
            bankTitle.textContent = bankData.bank.name;
            bankSection.appendChild(bankTitle);
            
            const optionsList = document.createElement("div");
            optionsList.className = "installment-options";
            
            bankData.installments.forEach(option => {
                const label = document.createElement("label");
                label.className = "installment-option";
                
                const radio = document.createElement("input");
                radio.type = "radio";
                radio.name = "installment";
                radio.value = option.installment_count;
                radio.className = "installment-radio";
                
                if (option.installment_count === 1) {
                    radio.checked = true;
                }
                
                const text = document.createElement("span");
                if (option.installment_count === 1) {
                    text.textContent = `Peşin - ${option.total_amount.toFixed(2)} TL`;
                } else {
                    text.textContent = `${option.installment_count} Taksit - ` +
                                      `${option.installment_amount.toFixed(2)} TL x ${option.installment_count} = ` +
                                      `${option.total_amount.toFixed(2)} TL`;
                    
                    if (option.interest_rate > 0) {
                        text.textContent += ` (Faiz: %${option.interest_rate.toFixed(2)})`;
                    }
                }
                
                label.appendChild(radio);
                label.appendChild(text);
                optionsList.appendChild(label);
            });
            
            bankSection.appendChild(optionsList);
            container.appendChild(bankSection);
        });
        
        container.style.display = "block";
    },
    
    /**
     * Show installments loading state.
     */
    _showInstallmentsLoading() {
        const container = this.el?.querySelector("#installments_container");
        if (container) {
            container.innerHTML = '<p class="text-muted"><i class="fa fa-spinner fa-spin"></i> Taksit seçenekleri yükleniyor...</p>';
            container.style.display = "block";
        }
    },
    
    /**
     * Clear installments display.
     */
    _clearInstallments() {
        const container = this.el?.querySelector("#installments_container");
        if (container) {
            container.innerHTML = "";
            container.style.display = "none";
        }
        this._selectedInstallment = 1;
    },
    
    /**
     * Toggle card form visibility based on payment method.
     */
    _toggleCardForm() {
        const cardForm = this.el?.querySelector("#card_form_container");
        const methodSelect = this.el?.querySelector("#payment_method");
        
        if (!cardForm || !methodSelect) return;
        
        const selectedOption = methodSelect.options[methodSelect.selectedIndex];
        const paymentType = selectedOption?.dataset?.paymentType;
        
        if (paymentType === "card") {
            cardForm.style.display = "block";
        } else {
            cardForm.style.display = "none";
        }
    },
    
    /**
     * Update card preview element (null-guarded).
     */
    _updateCardPreview(field, value) {
        const preview = this.el?.querySelector("#card_preview");
        if (!preview) return;
        
        const fieldElement = preview.querySelector(`[data-field="${field}"]`);
        if (fieldElement) {
            fieldElement.textContent = value || "";
        }
    },
    
    /**
     * Detect and display card brand from number.
     */
    _detectCardBrand(cardNumber) {
        const brandElement = this.el?.querySelector("#card_brand");
        if (!brandElement) return;
        
        let brand = "unknown";
        if (cardNumber.startsWith("4")) {
            brand = "visa";
        } else if (cardNumber.startsWith("5")) {
            brand = "mastercard";
        } else if (cardNumber.startsWith("9792")) {
            brand = "troy";
        }
        
        brandElement.textContent = brand.toUpperCase();
        brandElement.className = `card-brand brand-${brand}`;
    },
    
    /**
     * Show validation errors.
     */
    _showErrors(errors) {
        const errorContainer = this.el?.querySelector("#payment_errors");
        if (!errorContainer) {
            alert(errors.join("\n"));
            return;
        }
        
        errorContainer.innerHTML = "";
        errors.forEach(error => {
            const errorDiv = document.createElement("div");
            errorDiv.className = "alert alert-danger";
            errorDiv.textContent = error;
            errorContainer.appendChild(errorDiv);
        });
        
        errorContainer.style.display = "block";
        errorContainer.scrollIntoView({ behavior: "smooth" });
    },
    
    /**
     * Show single error message.
     */
    _showError(message) {
        this._showErrors([message]);
    },
    
    /**
     * Show success message.
     */
    _showSuccess(message) {
        const container = this.el?.querySelector("#payment_messages");
        if (!container) {
            alert(message);
            return;
        }
        
        const successDiv = document.createElement("div");
        successDiv.className = "alert alert-success";
        successDiv.textContent = message;
        
        container.innerHTML = "";
        container.appendChild(successDiv);
        container.style.display = "block";
    },
    
    // ========================================================================
    // UTILITY METHODS
    // ========================================================================
    
    /**
     * Get payment amount from page.
     */
    _getAmount() {
        const amountInput = this.el?.querySelector("#payment_amount");
        if (amountInput) {
            return parseFloat(amountInput.value) || 0;
        }
        
        // Fallback: try to get from order summary
        const orderTotal = document.querySelector(".order_total .oe_currency_value");
        if (orderTotal) {
            return parseFloat(orderTotal.textContent.replace(/[^0-9.]/g, "")) || 0;
        }
        
        return 0;
    },
    
    /**
     * Get currency ID.
     */
    _getCurrencyId() {
        const currencyInput = this.el?.querySelector("#payment_currency_id");
        return currencyInput ? parseInt(currencyInput.value) : null;
    },
    
    /**
     * Generate unique transaction reference.
     */
    _generateReference() {
        return `PAY-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    },
    
    /**
     * Get card data from form.
     */
    _getCardData() {
        return {
            card_number: this.el?.querySelector("#card_number")?.value.replace(/\D/g, "") || "",
            card_holder_name: this.el?.querySelector("#card_holder_name")?.value || "",
            expiry_month: this.el?.querySelector("#expiry_month")?.value || "",
            expiry_year: this.el?.querySelector("#expiry_year")?.value || "",
            cvv: this.el?.querySelector("#cvv")?.value || "",
        };
    },
    
    /**
     * Get complete payment data for submission.
     */
    _getPaymentData() {
        return {
            method_id: this._currentMethodId,
            amount: this._amount,
            currency_id: this._currencyId,
            reference: this._reference,
            card_data: this._getCardData(),
            installments: this._selectedInstallment,
        };
    },
});

// Register widget
publicWidget.registry.AbstractPaymentForm = AbstractPaymentForm;

export default AbstractPaymentForm;
