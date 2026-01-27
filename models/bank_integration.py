# -*- coding: utf-8 -*-
"""
Bank / Gateway integration classes for Turkish Virtual POS.

These are plain Python classes (NOT Odoo models).  They encapsulate the
communication protocol for each supported gateway and are instantiated at
runtime via the ``get_bank_integration()`` factory function.
"""

import hashlib
import base64
import hmac
import json
import logging
import uuid
from abc import ABC, abstractmethod

import requests

_logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
#  Base class
# ═══════════════════════════════════════════════════════════════════════

class BankIntegrationBase(ABC):
    """Abstract base for all bank gateway integrations."""

    def __init__(self, gateway, bank=None):
        """
        :param gateway: turkish.pos.gateway recordset (singleton).
        :param bank:    turkish.pos.bank recordset (singleton) or None.
        """
        self.gateway = gateway
        self.bank = bank
        self.credentials = gateway.get_credentials() if gateway else {}
        self.environment = gateway.environment if gateway else 'test'
        self.payment_model = gateway.payment_model if gateway else '3d_secure'

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _format_amount(amount, decimal_places=2):
        """Format amount to a string with the given decimal places.

        :param float amount: The amount.
        :param int decimal_places: Number of decimals.
        :return: str
        """
        return f"{amount:.{decimal_places}f}"

    @staticmethod
    def _generate_hash(data, encoding='utf-8'):
        """Generate SHA-1 hash of the given string data.

        :param str data: Input string.
        :param str encoding: Character encoding (default utf-8).
        :return: str - base64-encoded hash.
        """
        hash_bytes = hashlib.sha1(data.encode(encoding)).digest()
        return base64.b64encode(hash_bytes).decode(encoding)

    @staticmethod
    def _generate_sha256(data, encoding='utf-8'):
        """Generate SHA-256 hash of the given string data.

        :param str data: Input string.
        :param str encoding: Character encoding (default utf-8).
        :return: str - base64-encoded hash.
        """
        hash_bytes = hashlib.sha256(data.encode(encoding)).digest()
        return base64.b64encode(hash_bytes).decode(encoding)

    @staticmethod
    def _generate_sha512(data, encoding='utf-8'):
        """Generate SHA-512 hash of the given string data.

        :param str data: Input string.
        :param str encoding: Character encoding (default utf-8).
        :return: str - base64-encoded hash.
        """
        hash_bytes = hashlib.sha512(data.encode(encoding)).digest()
        return base64.b64encode(hash_bytes).decode(encoding)

    @staticmethod
    def _generate_hmac_sha256(key, data, encoding='utf-8'):
        """Generate HMAC-SHA256 of the data using the given key.

        :param str key: Secret key.
        :param str data: Input string.
        :param str encoding: Character encoding.
        :return: str - base64-encoded HMAC.
        """
        mac = hmac.new(
            key.encode(encoding),
            data.encode(encoding),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(mac).decode(encoding)

    @staticmethod
    def _generate_hmac_sha512(key, data, encoding='utf-8'):
        """Generate HMAC-SHA512 of the data using the given key.

        :param str key: Secret key.
        :param str data: Input string.
        :param str encoding: Character encoding.
        :return: str - base64-encoded HMAC.
        """
        mac = hmac.new(
            key.encode(encoding),
            data.encode(encoding),
            hashlib.sha512,
        ).digest()
        return base64.b64encode(mac).decode(encoding)

    def _make_request(self, url, method='POST', data=None, headers=None,
                      timeout=30, is_json=True):
        """Make an HTTP request and return the response.

        :param str url: Target URL.
        :param str method: HTTP method (GET / POST).
        :param dict data: Request payload.
        :param dict headers: Extra headers.
        :param int timeout: Timeout in seconds.
        :param bool is_json: If True, send/receive JSON; otherwise form data.
        :return: dict with ``success``, ``data``, ``status_code``, ``error``.
        """
        _logger.info("HTTP %s istegi: %s", method, url)
        try:
            if method.upper() == 'GET':
                response = requests.get(
                    url, params=data, headers=headers, timeout=timeout,
                )
            else:
                if is_json:
                    response = requests.post(
                        url, json=data, headers=headers, timeout=timeout,
                    )
                else:
                    response = requests.post(
                        url, data=data, headers=headers, timeout=timeout,
                    )

            _logger.debug("HTTP yanit kodu: %d", response.status_code)

            try:
                response_data = response.json()
            except (json.JSONDecodeError, ValueError):
                response_data = response.text

            return {
                'success': 200 <= response.status_code < 300,
                'data': response_data,
                'status_code': response.status_code,
                'error': None,
            }

        except requests.Timeout:
            _logger.error("HTTP istek zaman asimi: %s", url)
            return {
                'success': False,
                'data': None,
                'status_code': 0,
                'error': 'Baglanti zaman asimina ugradi.',
            }
        except requests.ConnectionError as e:
            _logger.error("HTTP baglanti hatasi: %s - %s", url, str(e))
            return {
                'success': False,
                'data': None,
                'status_code': 0,
                'error': f'Baglanti hatasi: {e}',
            }
        except Exception as e:
            _logger.exception("HTTP istek hatasi: %s", str(e))
            return {
                'success': False,
                'data': None,
                'status_code': 0,
                'error': str(e),
            }

    # ── Abstract interface ─────────────────────────────────────────────

    @abstractmethod
    def create_payment_form(self, amount, currency, installment_count,
                            order_id, transaction_id, success_url,
                            fail_url, callback_url, **kwargs):
        """Create the 3D Secure payment form HTML.

        :return: dict with ``success`` (bool) and ``html_form`` or error keys.
        """

    @abstractmethod
    def process_3d_response(self, notification_data):
        """Process the 3D Secure callback response from the bank.

        :param dict notification_data: POST data from the bank callback.
        :return: dict with transaction result details.
        """

    @abstractmethod
    def refund(self, transaction_id, bank_order_id, auth_code,
               amount, currency, **kwargs):
        """Process a refund.

        :return: dict with ``success`` (bool) and result details.
        """

    @abstractmethod
    def cancel(self, transaction_id, bank_order_id, auth_code,
               amount, currency, **kwargs):
        """Cancel (void) a transaction.

        :return: dict with ``success`` (bool) and result details.
        """


# ═══════════════════════════════════════════════════════════════════════
#  Param (Turk POS) Integration  --  SOAP via zeep
# ═══════════════════════════════════════════════════════════════════════

class ParamIntegration(BankIntegrationBase):
    """Param (Turk POS) SOAP-based integration."""

    TEST_WSDL = (
        'https://testposws.param.com.tr'
        '/turkpos.ws/service_turkpos_prod.asmx?wsdl'
    )
    PROD_WSDL = (
        'https://posws.param.com.tr'
        '/turkpos.ws/service_turkpos_prod.asmx?wsdl'
    )

    def _get_wsdl_url(self):
        return self.PROD_WSDL if self.environment == 'production' else self.TEST_WSDL

    def _get_client(self):
        """Return a zeep SOAP client."""
        try:
            from zeep import Client
            from zeep.transports import Transport
            transport = Transport(timeout=30)
            client = Client(wsdl=self._get_wsdl_url(), transport=transport)
            return client
        except ImportError:
            _logger.error(
                "zeep kutuphanesi yuklu degil. "
                "Param entegrasyonu icin 'pip install zeep' calistirin."
            )
            raise
        except Exception as e:
            _logger.error("Param SOAP istemci olusturma hatasi: %s", str(e))
            raise

    def _get_auth_params(self):
        """Return Param authentication parameters from credentials."""
        return {
            'CLIENT_CODE': self.credentials.get('clientCode', ''),
            'CLIENT_USERNAME': self.credentials.get('username', ''),
            'CLIENT_PASSWORD': self.credentials.get('password', ''),
            'GUID': self.credentials.get('guid', ''),
        }

    def create_payment_form(self, amount, currency, installment_count,
                            order_id, transaction_id, success_url,
                            fail_url, callback_url, **kwargs):
        _logger.info(
            "Param odeme formu olusturuluyor: tutar=%.2f, taksit=%d",
            amount, installment_count,
        )
        try:
            client = self._get_client()
            auth = self._get_auth_params()

            # TP_WMD_UCD -- 3D Secure payment initiation
            params = {
                'CLIENT_CODE': auth['CLIENT_CODE'],
                'CLIENT_USERNAME': auth['CLIENT_USERNAME'],
                'CLIENT_PASSWORD': auth['CLIENT_PASSWORD'],
                'GUID': auth['GUID'],
                'KK_No': kwargs.get('card_number', ''),
                'KK_SK_Ay': kwargs.get('card_exp_month', ''),
                'KK_SK_Yil': kwargs.get('card_exp_year', ''),
                'KK_CVC': kwargs.get('card_cvv', ''),
                'KK_Sahibi': kwargs.get('card_holder', ''),
                'Hata_URL': fail_url,
                'Basarili_URL': success_url,
                'Siparis_ID': order_id,
                'Siparis_Aciklama': kwargs.get('description', order_id),
                'Taksit': str(installment_count),
                'Islem_Tutar': self._format_amount(amount),
                'Toplam_Tutar': self._format_amount(amount),
                'Islem_Hash': '',
                'Islem_Guvenlik_Tip': '3D',
                'Islem_ID': transaction_id,
                'IPAdr': kwargs.get('ip_address', '127.0.0.1'),
                'Ref_URL': callback_url,
                'Data1': '',
                'Data2': '',
                'Data3': '',
                'Data4': '',
                'Data5': '',
            }

            result = client.service.TP_WMD_UCD(**params)

            if hasattr(result, 'UCD_HTML') and result.UCD_HTML:
                _logger.info("Param 3D formu basariyla alindi.")
                return {
                    'success': True,
                    'html_form': result.UCD_HTML,
                }
            else:
                error = getattr(result, 'UCD_MD', '') or \
                        getattr(result, 'Sonuc_Str', 'Bilinmeyen hata')
                _logger.warning("Param 3D form olusturma hatasi: %s", error)
                return {
                    'success': False,
                    'error_message': str(error),
                    'error_code': getattr(result, 'Sonuc', ''),
                }

        except Exception as e:
            _logger.exception("Param odeme formu hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'PARAM_ERROR',
            }

    def process_3d_response(self, notification_data):
        _logger.info("Param 3D yaniti isleniyor...")
        try:
            client = self._get_client()
            auth = self._get_auth_params()

            # Extract Param-specific fields from callback
            merchant_data = notification_data.get(
                'TURKPOS_RETVAL_Siparis_ID', ''
            )
            islem_guvenlik = notification_data.get(
                'TURKPOS_RETVAL_Islem_Guvenlik', ''
            )
            islem_hash = notification_data.get(
                'TURKPOS_RETVAL_Islem_Hash', ''
            )
            sonuc = notification_data.get('TURKPOS_RETVAL_Sonuc', '')
            sonuc_str = notification_data.get('TURKPOS_RETVAL_Sonuc_Str', '')

            # Validate 3D response
            if sonuc != '1':
                return {
                    'success': False,
                    'error_message': sonuc_str or 'Param 3D dogrulama basarisiz',
                    'error_code': sonuc,
                    'response_code': sonuc,
                    'response_message': sonuc_str,
                    'md_status': '',
                }

            # Complete the payment via TP_WMD_Pay
            pay_params = {
                'CLIENT_CODE': auth['CLIENT_CODE'],
                'CLIENT_USERNAME': auth['CLIENT_USERNAME'],
                'CLIENT_PASSWORD': auth['CLIENT_PASSWORD'],
                'GUID': auth['GUID'],
                'UCD_MD': islem_guvenlik,
                'Islem_GUID': islem_hash,
                'Siparis_ID': merchant_data,
            }

            pay_result = client.service.TP_WMD_Pay(**pay_params)

            if hasattr(pay_result, 'Sonuc') and str(pay_result.Sonuc) == '1':
                return {
                    'success': True,
                    'response_code': str(pay_result.Sonuc),
                    'response_message': getattr(pay_result, 'Sonuc_Str', ''),
                    'bank_order_id': merchant_data,
                    'auth_code': getattr(pay_result, 'Bank_Sonuc_Kod', ''),
                    'rrn': getattr(pay_result, 'Dekont_ID', ''),
                    'host_ref_num': getattr(pay_result, 'Dekont_ID', ''),
                    'md_status': '1',
                    'threed_status': 'success',
                }
            else:
                return {
                    'success': False,
                    'error_message': getattr(
                        pay_result, 'Sonuc_Str', 'Odeme tamamlanamadi'
                    ),
                    'error_code': str(getattr(pay_result, 'Sonuc', '')),
                    'response_code': str(getattr(pay_result, 'Sonuc', '')),
                    'response_message': getattr(pay_result, 'Sonuc_Str', ''),
                    'bank_order_id': merchant_data,
                }

        except Exception as e:
            _logger.exception("Param 3D yanit isleme hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'PARAM_3D_ERROR',
            }

    def refund(self, transaction_id, bank_order_id, auth_code,
               amount, currency, **kwargs):
        _logger.info(
            "Param iade islemi: siparis=%s, tutar=%.2f",
            bank_order_id, amount,
        )
        try:
            client = self._get_client()
            auth = self._get_auth_params()

            params = {
                'CLIENT_CODE': auth['CLIENT_CODE'],
                'CLIENT_USERNAME': auth['CLIENT_USERNAME'],
                'CLIENT_PASSWORD': auth['CLIENT_PASSWORD'],
                'GUID': auth['GUID'],
                'Durum': 'IADE',
                'Siparis_ID': bank_order_id,
                'Tutar': self._format_amount(amount),
            }

            result = client.service.TP_Islem_Iptal_Iade(**params)

            if hasattr(result, 'Sonuc') and str(result.Sonuc) == '1':
                return {
                    'success': True,
                    'response_code': str(result.Sonuc),
                    'response_message': getattr(result, 'Sonuc_Str', ''),
                }
            else:
                return {
                    'success': False,
                    'error_message': getattr(
                        result, 'Sonuc_Str', 'Iade basarisiz'
                    ),
                    'error_code': str(getattr(result, 'Sonuc', '')),
                }

        except Exception as e:
            _logger.exception("Param iade hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'PARAM_REFUND_ERROR',
            }

    def cancel(self, transaction_id, bank_order_id, auth_code,
               amount, currency, **kwargs):
        _logger.info(
            "Param iptal islemi: siparis=%s, tutar=%.2f",
            bank_order_id, amount,
        )
        try:
            client = self._get_client()
            auth = self._get_auth_params()

            params = {
                'CLIENT_CODE': auth['CLIENT_CODE'],
                'CLIENT_USERNAME': auth['CLIENT_USERNAME'],
                'CLIENT_PASSWORD': auth['CLIENT_PASSWORD'],
                'GUID': auth['GUID'],
                'Durum': 'IPTAL',
                'Siparis_ID': bank_order_id,
                'Tutar': self._format_amount(amount),
            }

            result = client.service.TP_Islem_Iptal_Iade(**params)

            if hasattr(result, 'Sonuc') and str(result.Sonuc) == '1':
                return {
                    'success': True,
                    'response_code': str(result.Sonuc),
                    'response_message': getattr(result, 'Sonuc_Str', ''),
                }
            else:
                return {
                    'success': False,
                    'error_message': getattr(
                        result, 'Sonuc_Str', 'Iptal basarisiz'
                    ),
                    'error_code': str(getattr(result, 'Sonuc', '')),
                }

        except Exception as e:
            _logger.exception("Param iptal hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'PARAM_CANCEL_ERROR',
            }


# ═══════════════════════════════════════════════════════════════════════
#  Tosla (Akbank Fintek) Integration  --  REST / JSON
# ═══════════════════════════════════════════════════════════════════════

class ToslaIntegration(BankIntegrationBase):
    """Tosla (Akbank Fintek) REST API integration."""

    TEST_URL = 'https://preprod.tosla.com/api'
    PROD_URL = 'https://api.tosla.com/api'

    def _get_base_url(self):
        return self.PROD_URL if self.environment == 'production' else self.TEST_URL

    def _get_headers(self):
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'clientId': self.credentials.get('clientId', ''),
            'apiUser': self.credentials.get('apiUser', ''),
        }

    def _generate_tosla_hash(self, params_str):
        """Generate Tosla-specific HMAC hash."""
        api_pass = self.credentials.get('apiPassword', '')
        return self._generate_hmac_sha512(api_pass, params_str)

    def create_payment_form(self, amount, currency, installment_count,
                            order_id, transaction_id, success_url,
                            fail_url, callback_url, **kwargs):
        _logger.info(
            "Tosla odeme formu olusturuluyor: tutar=%.2f, taksit=%d",
            amount, installment_count,
        )
        try:
            url = f"{self._get_base_url()}/Payment/threeDSecure"
            amount_kurus = int(round(amount * 100))

            hash_str = (
                f"{self.credentials.get('clientId', '')}"
                f"{amount_kurus}"
                f"{order_id}"
            )
            token = self._generate_tosla_hash(hash_str)

            payload = {
                'clientId': self.credentials.get('clientId', ''),
                'amount': amount_kurus,
                'currency': self._get_currency_code(currency),
                'installmentCount': installment_count,
                'orderId': order_id,
                'transactionId': transaction_id,
                'callbackUrl': callback_url,
                'successUrl': success_url,
                'failUrl': fail_url,
                'cardNumber': kwargs.get('card_number', ''),
                'cardExpireMonth': kwargs.get('card_exp_month', ''),
                'cardExpireYear': kwargs.get('card_exp_year', ''),
                'cardCvv': kwargs.get('card_cvv', ''),
                'cardHolderName': kwargs.get('card_holder', ''),
                'token': token,
            }

            result = self._make_request(
                url, data=payload, headers=self._get_headers(),
            )

            if result['success'] and result['data']:
                resp = result['data']
                if isinstance(resp, dict):
                    if resp.get('isSucceed') or resp.get('threeDContent'):
                        return {
                            'success': True,
                            'html_form': resp.get('threeDContent', ''),
                        }
                    else:
                        return {
                            'success': False,
                            'error_message': resp.get(
                                'message', 'Tosla 3D form hatasi'
                            ),
                            'error_code': resp.get('errorCode', ''),
                        }

            return {
                'success': False,
                'error_message': result.get('error', 'Tosla baglanti hatasi'),
                'error_code': 'TOSLA_ERROR',
            }

        except Exception as e:
            _logger.exception("Tosla odeme formu hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'TOSLA_ERROR',
            }

    def process_3d_response(self, notification_data):
        _logger.info("Tosla 3D yaniti isleniyor...")
        try:
            order_id = notification_data.get('orderId', '')
            hash_data = notification_data.get('hashData', '')
            status = notification_data.get('status', '')

            if status != '1':
                return {
                    'success': False,
                    'error_message': notification_data.get(
                        'errorMessage', 'Tosla odeme basarisiz'
                    ),
                    'error_code': notification_data.get('errorCode', ''),
                    'response_code': status,
                    'response_message': notification_data.get('errorMessage', ''),
                    'bank_order_id': order_id,
                }

            return {
                'success': True,
                'response_code': status,
                'response_message': 'Basarili',
                'bank_order_id': order_id,
                'auth_code': notification_data.get('authCode', ''),
                'rrn': notification_data.get('rrn', ''),
                'host_ref_num': notification_data.get('hostRefNum', ''),
                'md_status': notification_data.get('mdStatus', ''),
                'threed_status': 'success',
                'masked_card_number': notification_data.get('maskedCardNumber', ''),
            }

        except Exception as e:
            _logger.exception("Tosla 3D yanit hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'TOSLA_3D_ERROR',
            }

    def refund(self, transaction_id, bank_order_id, auth_code,
               amount, currency, **kwargs):
        _logger.info(
            "Tosla iade islemi: siparis=%s, tutar=%.2f",
            bank_order_id, amount,
        )
        try:
            url = f"{self._get_base_url()}/Payment/refund"
            amount_kurus = int(round(amount * 100))

            payload = {
                'clientId': self.credentials.get('clientId', ''),
                'orderId': bank_order_id,
                'amount': amount_kurus,
            }

            result = self._make_request(
                url, data=payload, headers=self._get_headers(),
            )

            if result['success'] and isinstance(result['data'], dict):
                resp = result['data']
                if resp.get('isSucceed'):
                    return {
                        'success': True,
                        'response_code': resp.get('resultCode', ''),
                        'response_message': resp.get('message', ''),
                    }
                return {
                    'success': False,
                    'error_message': resp.get('message', 'Iade basarisiz'),
                    'error_code': resp.get('errorCode', ''),
                }

            return {
                'success': False,
                'error_message': result.get('error', 'Tosla baglanti hatasi'),
                'error_code': 'TOSLA_REFUND_ERROR',
            }

        except Exception as e:
            _logger.exception("Tosla iade hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'TOSLA_REFUND_ERROR',
            }

    def cancel(self, transaction_id, bank_order_id, auth_code,
               amount, currency, **kwargs):
        _logger.info(
            "Tosla iptal islemi: siparis=%s", bank_order_id,
        )
        try:
            url = f"{self._get_base_url()}/Payment/void"

            payload = {
                'clientId': self.credentials.get('clientId', ''),
                'orderId': bank_order_id,
            }

            result = self._make_request(
                url, data=payload, headers=self._get_headers(),
            )

            if result['success'] and isinstance(result['data'], dict):
                resp = result['data']
                if resp.get('isSucceed'):
                    return {
                        'success': True,
                        'response_code': resp.get('resultCode', ''),
                        'response_message': resp.get('message', ''),
                    }
                return {
                    'success': False,
                    'error_message': resp.get('message', 'Iptal basarisiz'),
                    'error_code': resp.get('errorCode', ''),
                }

            return {
                'success': False,
                'error_message': result.get('error', 'Tosla baglanti hatasi'),
                'error_code': 'TOSLA_CANCEL_ERROR',
            }

        except Exception as e:
            _logger.exception("Tosla iptal hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'TOSLA_CANCEL_ERROR',
            }

    @staticmethod
    def _get_currency_code(currency):
        mapping = {'TRY': 949, 'USD': 840, 'EUR': 978}
        return mapping.get(currency, 949)


# ═══════════════════════════════════════════════════════════════════════
#  iyzico Integration  --  REST / JSON
# ═══════════════════════════════════════════════════════════════════════

class IyzicoIntegration(BankIntegrationBase):
    """iyzico REST API integration."""

    SANDBOX_URL = 'https://sandbox-api.iyzipay.com'
    PROD_URL = 'https://api.iyzipay.com'

    def _get_base_url(self):
        return self.PROD_URL if self.environment == 'production' else self.SANDBOX_URL

    def _get_headers(self, authorization):
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': authorization,
        }

    def _generate_iyzico_auth(self, uri, request_body=''):
        """Generate iyzico Authorization header value.

        iyzico uses a custom scheme:
        Authorization: IYZWS {apiKey}:{hash}
        where hash = Base64(SHA1(apiKey + random + secretKey + requestBody))
        """
        api_key = self.credentials.get('apiKey', '')
        secret_key = self.credentials.get('secretKey', '')
        random_str = str(uuid.uuid4()).replace('-', '')[:8]

        hash_str = f"{api_key}{random_str}{secret_key}{request_body}"
        hash_value = self._generate_hash(hash_str)

        return f"IYZWS {api_key}:{hash_value}"

    def create_payment_form(self, amount, currency, installment_count,
                            order_id, transaction_id, success_url,
                            fail_url, callback_url, **kwargs):
        _logger.info(
            "iyzico odeme formu olusturuluyor: tutar=%.2f, taksit=%d",
            amount, installment_count,
        )
        try:
            url = f"{self._get_base_url()}/payment/3dsecure/initialize"

            price_str = self._format_amount(amount)

            payload = {
                'locale': 'tr',
                'conversationId': transaction_id,
                'price': price_str,
                'paidPrice': price_str,
                'currency': currency,
                'installment': installment_count,
                'basketId': order_id,
                'paymentChannel': 'WEB',
                'paymentGroup': 'PRODUCT',
                'paymentCard': {
                    'cardHolderName': kwargs.get('card_holder', ''),
                    'cardNumber': kwargs.get('card_number', ''),
                    'expireMonth': kwargs.get('card_exp_month', ''),
                    'expireYear': kwargs.get('card_exp_year', ''),
                    'cvc': kwargs.get('card_cvv', ''),
                },
                'buyer': kwargs.get('buyer', {
                    'id': 'BUYER_1',
                    'name': kwargs.get('buyer_name', 'Musteri'),
                    'surname': kwargs.get('buyer_surname', ''),
                    'email': kwargs.get('buyer_email', ''),
                    'identityNumber': kwargs.get('buyer_identity', '11111111111'),
                    'registrationAddress': kwargs.get('buyer_address', 'Istanbul'),
                    'ip': kwargs.get('ip_address', '127.0.0.1'),
                    'city': kwargs.get('buyer_city', 'Istanbul'),
                    'country': kwargs.get('buyer_country', 'Turkey'),
                }),
                'shippingAddress': kwargs.get('shipping_address', {
                    'contactName': kwargs.get('card_holder', ''),
                    'city': 'Istanbul',
                    'country': 'Turkey',
                    'address': kwargs.get('buyer_address', 'Istanbul'),
                }),
                'billingAddress': kwargs.get('billing_address', {
                    'contactName': kwargs.get('card_holder', ''),
                    'city': 'Istanbul',
                    'country': 'Turkey',
                    'address': kwargs.get('buyer_address', 'Istanbul'),
                }),
                'basketItems': kwargs.get('basket_items', [{
                    'id': order_id,
                    'name': 'Siparis',
                    'category1': 'Urun',
                    'itemType': 'PHYSICAL',
                    'price': price_str,
                }]),
                'callbackUrl': callback_url,
            }

            body_json = json.dumps(payload)
            auth = self._generate_iyzico_auth(url, body_json)

            result = self._make_request(
                url, data=payload,
                headers=self._get_headers(auth),
            )

            if result['success'] and isinstance(result['data'], dict):
                resp = result['data']
                if resp.get('status') == 'success':
                    return {
                        'success': True,
                        'html_form': resp.get('threeDSHtmlContent', ''),
                    }
                return {
                    'success': False,
                    'error_message': resp.get(
                        'errorMessage', 'iyzico 3D form hatasi'
                    ),
                    'error_code': resp.get('errorCode', ''),
                }

            return {
                'success': False,
                'error_message': result.get('error', 'iyzico baglanti hatasi'),
                'error_code': 'IYZICO_ERROR',
            }

        except Exception as e:
            _logger.exception("iyzico odeme formu hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'IYZICO_ERROR',
            }

    def process_3d_response(self, notification_data):
        _logger.info("iyzico 3D yaniti isleniyor...")
        try:
            status = notification_data.get('status', '')
            payment_id = notification_data.get('paymentId', '')
            conversation_id = notification_data.get('conversationId', '')

            if status != 'success':
                return {
                    'success': False,
                    'error_message': notification_data.get(
                        'errorMessage', 'iyzico odeme basarisiz'
                    ),
                    'error_code': notification_data.get('errorCode', ''),
                    'response_code': status,
                    'response_message': notification_data.get('errorMessage', ''),
                    'bank_order_id': conversation_id,
                }

            # Complete 3D payment
            url = f"{self._get_base_url()}/payment/3dsecure/auth"
            payload = {
                'locale': 'tr',
                'conversationId': conversation_id,
                'paymentId': payment_id,
            }

            body_json = json.dumps(payload)
            auth = self._generate_iyzico_auth(url, body_json)

            result = self._make_request(
                url, data=payload,
                headers=self._get_headers(auth),
            )

            if result['success'] and isinstance(result['data'], dict):
                resp = result['data']
                if resp.get('status') == 'success':
                    return {
                        'success': True,
                        'response_code': '00',
                        'response_message': 'Basarili',
                        'bank_order_id': conversation_id,
                        'auth_code': resp.get('authCode', ''),
                        'rrn': str(resp.get('paymentId', '')),
                        'host_ref_num': str(resp.get('paymentId', '')),
                        'md_status': '1',
                        'threed_status': 'success',
                        'masked_card_number': resp.get(
                            'cardAssociation', ''
                        ),
                    }
                return {
                    'success': False,
                    'error_message': resp.get(
                        'errorMessage', 'iyzico 3D tamamlama basarisiz'
                    ),
                    'error_code': resp.get('errorCode', ''),
                    'response_code': resp.get('errorCode', ''),
                    'response_message': resp.get('errorMessage', ''),
                    'bank_order_id': conversation_id,
                }

            return {
                'success': False,
                'error_message': result.get('error', 'iyzico baglanti hatasi'),
                'error_code': 'IYZICO_3D_ERROR',
            }

        except Exception as e:
            _logger.exception("iyzico 3D yanit hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'IYZICO_3D_ERROR',
            }

    def refund(self, transaction_id, bank_order_id, auth_code,
               amount, currency, **kwargs):
        _logger.info(
            "iyzico iade islemi: siparis=%s, tutar=%.2f",
            bank_order_id, amount,
        )
        try:
            url = f"{self._get_base_url()}/payment/refund"
            price_str = self._format_amount(amount)

            payload = {
                'locale': 'tr',
                'conversationId': transaction_id,
                'paymentTransactionId': kwargs.get(
                    'payment_transaction_id', bank_order_id
                ),
                'price': price_str,
                'currency': currency,
            }

            body_json = json.dumps(payload)
            auth_header = self._generate_iyzico_auth(url, body_json)

            result = self._make_request(
                url, data=payload,
                headers=self._get_headers(auth_header),
            )

            if result['success'] and isinstance(result['data'], dict):
                resp = result['data']
                if resp.get('status') == 'success':
                    return {
                        'success': True,
                        'response_code': '00',
                        'response_message': 'Iade basarili',
                    }
                return {
                    'success': False,
                    'error_message': resp.get('errorMessage', 'Iade basarisiz'),
                    'error_code': resp.get('errorCode', ''),
                }

            return {
                'success': False,
                'error_message': result.get('error', 'iyzico baglanti hatasi'),
                'error_code': 'IYZICO_REFUND_ERROR',
            }

        except Exception as e:
            _logger.exception("iyzico iade hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'IYZICO_REFUND_ERROR',
            }

    def cancel(self, transaction_id, bank_order_id, auth_code,
               amount, currency, **kwargs):
        _logger.info(
            "iyzico iptal islemi: siparis=%s", bank_order_id,
        )
        try:
            url = f"{self._get_base_url()}/payment/cancel"

            payload = {
                'locale': 'tr',
                'conversationId': transaction_id,
                'paymentId': bank_order_id,
            }

            body_json = json.dumps(payload)
            auth_header = self._generate_iyzico_auth(url, body_json)

            result = self._make_request(
                url, data=payload,
                headers=self._get_headers(auth_header),
            )

            if result['success'] and isinstance(result['data'], dict):
                resp = result['data']
                if resp.get('status') == 'success':
                    return {
                        'success': True,
                        'response_code': '00',
                        'response_message': 'Iptal basarili',
                    }
                return {
                    'success': False,
                    'error_message': resp.get('errorMessage', 'Iptal basarisiz'),
                    'error_code': resp.get('errorCode', ''),
                }

            return {
                'success': False,
                'error_message': result.get('error', 'iyzico baglanti hatasi'),
                'error_code': 'IYZICO_CANCEL_ERROR',
            }

        except Exception as e:
            _logger.exception("iyzico iptal hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'IYZICO_CANCEL_ERROR',
            }


# ═══════════════════════════════════════════════════════════════════════
#  QNB Pay Integration  --  REST / JSON
# ═══════════════════════════════════════════════════════════════════════

class QnbPayIntegration(BankIntegrationBase):
    """QNB Pay (QNB Finansbank) REST API integration."""

    TEST_URL = 'https://vpostest.qnbfinansbank.com/Gateway/Default.aspx'
    PROD_URL = 'https://vpos.qnbfinansbank.com/Gateway/Default.aspx'

    def _get_base_url(self):
        return self.PROD_URL if self.environment == 'production' else self.TEST_URL

    def create_payment_form(self, amount, currency, installment_count,
                            order_id, transaction_id, success_url,
                            fail_url, callback_url, **kwargs):
        _logger.info(
            "QNB Pay odeme formu olusturuluyor: tutar=%.2f, taksit=%d",
            amount, installment_count,
        )
        try:
            merchant_id = self.credentials.get('merchantId', '')
            merchant_pass = self.credentials.get('merchantPassword', '')
            user_code = self.credentials.get('userCode', '')

            amount_str = self._format_amount(amount)
            currency_code = self._get_currency_code(currency)

            hash_data = (
                f"{merchant_id}{order_id}{amount_str}"
                f"{success_url}{fail_url}{merchant_pass}"
            )
            hash_value = self._generate_sha256(hash_data)

            form_data = {
                'MbrId': '5',
                'MerchantId': merchant_id,
                'UserCode': user_code,
                'UserPass': merchant_pass,
                'SecureType': '3DPay',
                'TxnType': 'Auth',
                'InstallmentCount': str(installment_count) if installment_count > 1 else '',
                'Currency': currency_code,
                'OkUrl': success_url,
                'FailUrl': fail_url,
                'OrderId': order_id,
                'PurchAmount': amount_str,
                'Lang': 'TR',
                'CardHolderName': kwargs.get('card_holder', ''),
                'Pan': kwargs.get('card_number', ''),
                'Expiry': (
                    kwargs.get('card_exp_month', '').zfill(2) +
                    kwargs.get('card_exp_year', '')[-2:]
                ),
                'Cvv2': kwargs.get('card_cvv', ''),
                'Hash': hash_value,
            }

            # Build auto-submit HTML form
            html = self._build_auto_submit_form(
                self._get_base_url(), form_data
            )
            return {
                'success': True,
                'html_form': html,
            }

        except Exception as e:
            _logger.exception("QNB Pay odeme formu hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'QNB_ERROR',
            }

    def process_3d_response(self, notification_data):
        _logger.info("QNB Pay 3D yaniti isleniyor...")
        try:
            proc_return_code = notification_data.get('ProcReturnCode', '')
            response = notification_data.get('Response', '')
            order_id = notification_data.get('OrderId', '')
            auth_code = notification_data.get('AuthCode', '')
            host_ref_num = notification_data.get('HostRefNum', '')

            md_status = notification_data.get('3DStatus', '')

            if proc_return_code == '00' and response == 'Approved':
                return {
                    'success': True,
                    'response_code': proc_return_code,
                    'response_message': response,
                    'bank_order_id': order_id,
                    'auth_code': auth_code,
                    'rrn': notification_data.get('Rrn', ''),
                    'host_ref_num': host_ref_num,
                    'md_status': md_status,
                    'eci': notification_data.get('Eci', ''),
                    'cavv': notification_data.get('Cavv', ''),
                    'xid': notification_data.get('Xid', ''),
                    'threed_status': 'success',
                    'masked_card_number': notification_data.get(
                        'MaskedPan', ''
                    ),
                }

            return {
                'success': False,
                'error_message': notification_data.get(
                    'ErrMsg', 'QNB Pay odeme basarisiz'
                ),
                'error_code': proc_return_code,
                'response_code': proc_return_code,
                'response_message': response,
                'bank_order_id': order_id,
                'md_status': md_status,
            }

        except Exception as e:
            _logger.exception("QNB Pay 3D yanit hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'QNB_3D_ERROR',
            }

    def refund(self, transaction_id, bank_order_id, auth_code,
               amount, currency, **kwargs):
        _logger.info(
            "QNB Pay iade islemi: siparis=%s, tutar=%.2f",
            bank_order_id, amount,
        )
        try:
            url = self._get_base_url()
            merchant_id = self.credentials.get('merchantId', '')
            merchant_pass = self.credentials.get('merchantPassword', '')

            form_data = {
                'MbrId': '5',
                'MerchantId': merchant_id,
                'UserPass': merchant_pass,
                'TxnType': 'Refund',
                'OrderId': bank_order_id,
                'PurchAmount': self._format_amount(amount),
                'Currency': self._get_currency_code(currency),
                'Lang': 'TR',
            }

            result = self._make_request(
                url, data=form_data, is_json=False,
            )

            if result['success']:
                resp_text = str(result.get('data', ''))
                if 'Approved' in resp_text:
                    return {
                        'success': True,
                        'response_code': '00',
                        'response_message': 'Iade basarili',
                    }
                return {
                    'success': False,
                    'error_message': resp_text[:200],
                    'error_code': 'QNB_REFUND_FAIL',
                }

            return {
                'success': False,
                'error_message': result.get('error', 'QNB baglanti hatasi'),
                'error_code': 'QNB_REFUND_ERROR',
            }

        except Exception as e:
            _logger.exception("QNB Pay iade hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'QNB_REFUND_ERROR',
            }

    def cancel(self, transaction_id, bank_order_id, auth_code,
               amount, currency, **kwargs):
        _logger.info(
            "QNB Pay iptal islemi: siparis=%s", bank_order_id,
        )
        try:
            url = self._get_base_url()
            merchant_id = self.credentials.get('merchantId', '')
            merchant_pass = self.credentials.get('merchantPassword', '')

            form_data = {
                'MbrId': '5',
                'MerchantId': merchant_id,
                'UserPass': merchant_pass,
                'TxnType': 'Void',
                'OrderId': bank_order_id,
                'PurchAmount': self._format_amount(amount),
                'Currency': self._get_currency_code(currency),
                'Lang': 'TR',
            }

            result = self._make_request(
                url, data=form_data, is_json=False,
            )

            if result['success']:
                resp_text = str(result.get('data', ''))
                if 'Approved' in resp_text:
                    return {
                        'success': True,
                        'response_code': '00',
                        'response_message': 'Iptal basarili',
                    }
                return {
                    'success': False,
                    'error_message': resp_text[:200],
                    'error_code': 'QNB_CANCEL_FAIL',
                }

            return {
                'success': False,
                'error_message': result.get('error', 'QNB baglanti hatasi'),
                'error_code': 'QNB_CANCEL_ERROR',
            }

        except Exception as e:
            _logger.exception("QNB Pay iptal hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'QNB_CANCEL_ERROR',
            }

    @staticmethod
    def _get_currency_code(currency):
        mapping = {'TRY': '949', 'USD': '840', 'EUR': '978'}
        return mapping.get(currency, '949')

    @staticmethod
    def _build_auto_submit_form(url, fields_dict):
        """Build an HTML form that auto-submits via JavaScript."""
        fields_html = ''
        for key, val in fields_dict.items():
            safe_val = str(val).replace('"', '&quot;')
            fields_html += (
                f'<input type="hidden" name="{key}" value="{safe_val}" />\n'
            )
        return (
            f'<html><body onload="document.getElementById(\'tpos_form\').submit();">'
            f'<form id="tpos_form" method="POST" action="{url}">'
            f'{fields_html}'
            f'<noscript><input type="submit" value="Devam Et" /></noscript>'
            f'</form></body></html>'
        )


# ═══════════════════════════════════════════════════════════════════════
#  Akbank Sanal POS Integration  --  EST v3 / XML-based
# ═══════════════════════════════════════════════════════════════════════

class AkbankIntegration(BankIntegrationBase):
    """Akbank Sanal POS integration (EST v3 / Asseco Payten)."""

    TEST_URL_3D = 'https://entegrasyon.asseco-see.com.tr/fim/est3Dgate'
    PROD_URL_3D = 'https://sanalpos.est.com.tr/fim/est3Dgate'
    TEST_URL_API = 'https://entegrasyon.asseco-see.com.tr/fim/api'
    PROD_URL_API = 'https://sanalpos.est.com.tr/fim/api'

    def _get_3d_url(self):
        return self.PROD_URL_3D if self.environment == 'production' else self.TEST_URL_3D

    def _get_api_url(self):
        return self.PROD_URL_API if self.environment == 'production' else self.TEST_URL_API

    def _generate_est_hash(self, params):
        """Generate EST v3 hash value."""
        store_key = self.credentials.get('storeKey', '')
        hash_str = '|'.join(str(v) for v in params) + '|' + store_key
        return self._generate_sha512(hash_str)

    def create_payment_form(self, amount, currency, installment_count,
                            order_id, transaction_id, success_url,
                            fail_url, callback_url, **kwargs):
        _logger.info(
            "Akbank (EST) odeme formu olusturuluyor: tutar=%.2f, taksit=%d",
            amount, installment_count,
        )
        try:
            client_id = self.credentials.get('clientId', '')
            store_key = self.credentials.get('storeKey', '')
            store_type = '3D_PAY'

            amount_str = self._format_amount(amount)
            currency_code = self._get_currency_code(currency)
            rnd = str(uuid.uuid4()).replace('-', '')[:20]

            hash_params = [
                client_id, order_id, amount_str, success_url,
                fail_url, store_type, str(installment_count),
                rnd, '', currency_code,
            ]
            hash_value = self._generate_est_hash(hash_params)

            form_data = {
                'clientid': client_id,
                'storetype': store_type,
                'hash': hash_value,
                'islemtipi': 'Auth',
                'amount': amount_str,
                'currency': currency_code,
                'oid': order_id,
                'okUrl': success_url,
                'failUrl': fail_url,
                'callbackUrl': callback_url,
                'lang': 'tr',
                'rnd': rnd,
                'pan': kwargs.get('card_number', ''),
                'Ecom_Payment_Card_ExpDate_Month': kwargs.get(
                    'card_exp_month', ''
                ),
                'Ecom_Payment_Card_ExpDate_Year': kwargs.get(
                    'card_exp_year', ''
                ),
                'cv2': kwargs.get('card_cvv', ''),
                'cardHolderName': kwargs.get('card_holder', ''),
                'taksit': str(installment_count) if installment_count > 1 else '',
            }

            html = QnbPayIntegration._build_auto_submit_form(
                self._get_3d_url(), form_data
            )
            return {
                'success': True,
                'html_form': html,
            }

        except Exception as e:
            _logger.exception("Akbank odeme formu hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'AKBANK_ERROR',
            }

    def process_3d_response(self, notification_data):
        _logger.info("Akbank (EST) 3D yaniti isleniyor...")
        try:
            md_status = notification_data.get('mdStatus', '')
            proc_return_code = notification_data.get('ProcReturnCode', '')
            response = notification_data.get('Response', '')
            order_id = notification_data.get('oid', '')

            # MD Status 1,2,3,4 are considered valid for different scenarios
            if md_status in ('1', '2', '3', '4') and proc_return_code == '00':
                return {
                    'success': True,
                    'response_code': proc_return_code,
                    'response_message': response,
                    'bank_order_id': order_id,
                    'auth_code': notification_data.get('AuthCode', ''),
                    'rrn': notification_data.get('rrn', ''),
                    'host_ref_num': notification_data.get('HostRefNum', ''),
                    'md_status': md_status,
                    'eci': notification_data.get('eci', ''),
                    'cavv': notification_data.get('cavv', ''),
                    'xid': notification_data.get('xid', ''),
                    'threed_status': 'success',
                    'masked_card_number': notification_data.get(
                        'MaskedPan', notification_data.get('maskedCreditCard', '')
                    ),
                }

            return {
                'success': False,
                'error_message': notification_data.get(
                    'ErrMsg', 'Akbank odeme basarisiz'
                ),
                'error_code': proc_return_code,
                'response_code': proc_return_code,
                'response_message': response,
                'bank_order_id': order_id,
                'md_status': md_status,
            }

        except Exception as e:
            _logger.exception("Akbank 3D yanit hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'AKBANK_3D_ERROR',
            }

    def refund(self, transaction_id, bank_order_id, auth_code,
               amount, currency, **kwargs):
        _logger.info(
            "Akbank iade islemi: siparis=%s, tutar=%.2f",
            bank_order_id, amount,
        )
        try:
            url = self._get_api_url()
            client_id = self.credentials.get('clientId', '')
            username = self.credentials.get('username', '')
            password = self.credentials.get('password', '')

            xml_data = (
                f'<?xml version="1.0" encoding="UTF-8"?>'
                f'<CC5Request>'
                f'<Name>{username}</Name>'
                f'<Password>{password}</Password>'
                f'<ClientId>{client_id}</ClientId>'
                f'<Type>Credit</Type>'
                f'<OrderId>{bank_order_id}</OrderId>'
                f'<Total>{self._format_amount(amount)}</Total>'
                f'<Currency>{self._get_currency_code(currency)}</Currency>'
                f'</CC5Request>'
            )

            result = self._make_request(
                url, data=xml_data,
                headers={'Content-Type': 'application/xml'},
                is_json=False,
            )

            resp_text = str(result.get('data', ''))
            if 'Approved' in resp_text:
                return {
                    'success': True,
                    'response_code': '00',
                    'response_message': 'Iade basarili',
                }
            return {
                'success': False,
                'error_message': resp_text[:200],
                'error_code': 'AKBANK_REFUND_FAIL',
            }

        except Exception as e:
            _logger.exception("Akbank iade hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'AKBANK_REFUND_ERROR',
            }

    def cancel(self, transaction_id, bank_order_id, auth_code,
               amount, currency, **kwargs):
        _logger.info(
            "Akbank iptal islemi: siparis=%s", bank_order_id,
        )
        try:
            url = self._get_api_url()
            client_id = self.credentials.get('clientId', '')
            username = self.credentials.get('username', '')
            password = self.credentials.get('password', '')

            xml_data = (
                f'<?xml version="1.0" encoding="UTF-8"?>'
                f'<CC5Request>'
                f'<Name>{username}</Name>'
                f'<Password>{password}</Password>'
                f'<ClientId>{client_id}</ClientId>'
                f'<Type>Void</Type>'
                f'<OrderId>{bank_order_id}</OrderId>'
                f'<Total>{self._format_amount(amount)}</Total>'
                f'<Currency>{self._get_currency_code(currency)}</Currency>'
                f'</CC5Request>'
            )

            result = self._make_request(
                url, data=xml_data,
                headers={'Content-Type': 'application/xml'},
                is_json=False,
            )

            resp_text = str(result.get('data', ''))
            if 'Approved' in resp_text:
                return {
                    'success': True,
                    'response_code': '00',
                    'response_message': 'Iptal basarili',
                }
            return {
                'success': False,
                'error_message': resp_text[:200],
                'error_code': 'AKBANK_CANCEL_FAIL',
            }

        except Exception as e:
            _logger.exception("Akbank iptal hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'AKBANK_CANCEL_ERROR',
            }

    @staticmethod
    def _get_currency_code(currency):
        mapping = {'TRY': '949', 'USD': '840', 'EUR': '978'}
        return mapping.get(currency, '949')


# ═══════════════════════════════════════════════════════════════════════
#  Garanti BBVA Integration
# ═══════════════════════════════════════════════════════════════════════

class GarantiIntegration(BankIntegrationBase):
    """Garanti BBVA Sanal POS integration."""

    TEST_URL_3D = 'https://sanalposprovtest.garanti.com.tr/servlet/gt3dengine'
    PROD_URL_3D = 'https://sanalposprov.garanti.com.tr/servlet/gt3dengine'
    TEST_URL_API = 'https://sanalposprovtest.garanti.com.tr/VPServlet'
    PROD_URL_API = 'https://sanalposprov.garanti.com.tr/VPServlet'

    def _get_3d_url(self):
        return self.PROD_URL_3D if self.environment == 'production' else self.TEST_URL_3D

    def _get_api_url(self):
        return self.PROD_URL_API if self.environment == 'production' else self.TEST_URL_API

    def _generate_garanti_hash(self, terminal_id, order_id, amount,
                               success_url, fail_url, txn_type,
                               installment, store_key, security_data):
        """Generate Garanti-specific SHA-512 hash."""
        hash_str = (
            f"{terminal_id}{order_id}{amount}{success_url}"
            f"{fail_url}{txn_type}{installment}{store_key}{security_data}"
        )
        return self._generate_sha512(hash_str)

    def create_payment_form(self, amount, currency, installment_count,
                            order_id, transaction_id, success_url,
                            fail_url, callback_url, **kwargs):
        _logger.info(
            "Garanti odeme formu olusturuluyor: tutar=%.2f, taksit=%d",
            amount, installment_count,
        )
        try:
            terminal_id = self.credentials.get('terminalId', '')
            merchant_id = self.credentials.get('merchantId', '')
            store_key = self.credentials.get('storeKey', '')
            prov_user_id = self.credentials.get('provUserPassword', '')

            amount_int = int(round(amount * 100))
            amount_str = str(amount_int)
            currency_code = self._get_currency_code(currency)

            # Security data = SHA512(password + terminal_id_padded)
            terminal_padded = terminal_id.zfill(9)
            security_data = self._generate_sha512(
                prov_user_id + terminal_padded
            )

            hash_value = self._generate_garanti_hash(
                terminal_id, order_id, amount_str,
                success_url, fail_url, 'sales',
                str(installment_count) if installment_count > 1 else '',
                store_key, security_data,
            )

            form_data = {
                'mode': 'TEST' if self.environment == 'test' else 'PROD',
                'apiversion': 'v0.01',
                'terminalprovuserid': 'PROVAUT',
                'terminaluserid': self.credentials.get('terminalUserId', ''),
                'terminalmerchantid': merchant_id,
                'terminalid': terminal_id,
                'txntype': 'sales',
                'txnamount': amount_str,
                'txncurrencycode': currency_code,
                'txninstallmentcount': (
                    str(installment_count) if installment_count > 1 else ''
                ),
                'orderid': order_id,
                'successurl': success_url,
                'errorurl': fail_url,
                'customeripaddress': kwargs.get('ip_address', '127.0.0.1'),
                'secure3dhash': hash_value,
                'secure3dsecuritylevel': '3D_PAY',
                'cardnumber': kwargs.get('card_number', ''),
                'cardexpiredatemonth': kwargs.get('card_exp_month', ''),
                'cardexpiredateyear': kwargs.get('card_exp_year', ''),
                'cardcvv2': kwargs.get('card_cvv', ''),
            }

            html = QnbPayIntegration._build_auto_submit_form(
                self._get_3d_url(), form_data
            )
            return {
                'success': True,
                'html_form': html,
            }

        except Exception as e:
            _logger.exception("Garanti odeme formu hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'GARANTI_ERROR',
            }

    def process_3d_response(self, notification_data):
        _logger.info("Garanti 3D yaniti isleniyor...")
        try:
            md_status = notification_data.get('mdstatus', '')
            response_code = notification_data.get('procreturncode', '')
            response_msg = notification_data.get('response', '')
            order_id = notification_data.get('orderid', '')

            if md_status in ('1', '2', '3', '4') and response_code == '00':
                return {
                    'success': True,
                    'response_code': response_code,
                    'response_message': response_msg,
                    'bank_order_id': order_id,
                    'auth_code': notification_data.get('authcode', ''),
                    'rrn': notification_data.get('rrn', ''),
                    'host_ref_num': notification_data.get('hostrefnum', ''),
                    'md_status': md_status,
                    'eci': notification_data.get('eci', ''),
                    'cavv': notification_data.get('cavv', ''),
                    'xid': notification_data.get('xid', ''),
                    'threed_status': 'success',
                    'masked_card_number': notification_data.get(
                        'MaskedPan', ''
                    ),
                }

            return {
                'success': False,
                'error_message': notification_data.get(
                    'errmsg', 'Garanti odeme basarisiz'
                ),
                'error_code': response_code,
                'response_code': response_code,
                'response_message': response_msg,
                'bank_order_id': order_id,
                'md_status': md_status,
            }

        except Exception as e:
            _logger.exception("Garanti 3D yanit hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'GARANTI_3D_ERROR',
            }

    def refund(self, transaction_id, bank_order_id, auth_code,
               amount, currency, **kwargs):
        _logger.info(
            "Garanti iade islemi: siparis=%s, tutar=%.2f",
            bank_order_id, amount,
        )
        try:
            url = self._get_api_url()
            terminal_id = self.credentials.get('terminalId', '')
            merchant_id = self.credentials.get('merchantId', '')
            prov_user_id = self.credentials.get('provUserPassword', '')

            amount_int = int(round(amount * 100))
            terminal_padded = terminal_id.zfill(9)
            security_data = self._generate_sha512(
                prov_user_id + terminal_padded
            )
            hash_data = (
                f"{bank_order_id}{terminal_id}{amount_int}{security_data}"
            )
            hash_value = self._generate_sha512(hash_data)

            xml_data = (
                f'<?xml version="1.0" encoding="UTF-8"?>'
                f'<GVPSRequest>'
                f'<Mode>{"TEST" if self.environment == "test" else "PROD"}</Mode>'
                f'<Version>v0.01</Version>'
                f'<Terminal>'
                f'<ProvUserID>PROVRFN</ProvUserID>'
                f'<HashData>{hash_value}</HashData>'
                f'<UserID>PROVRFN</UserID>'
                f'<ID>{terminal_id}</ID>'
                f'<MerchantID>{merchant_id}</MerchantID>'
                f'</Terminal>'
                f'<Order><OrderID>{bank_order_id}</OrderID></Order>'
                f'<Transaction>'
                f'<Type>refund</Type>'
                f'<Amount>{amount_int}</Amount>'
                f'<CurrencyCode>{self._get_currency_code(currency)}</CurrencyCode>'
                f'</Transaction>'
                f'</GVPSRequest>'
            )

            result = self._make_request(
                url, data=xml_data,
                headers={'Content-Type': 'application/xml'},
                is_json=False,
            )

            resp_text = str(result.get('data', ''))
            if 'Approved' in resp_text or '<Code>00</Code>' in resp_text:
                return {
                    'success': True,
                    'response_code': '00',
                    'response_message': 'Iade basarili',
                }
            return {
                'success': False,
                'error_message': resp_text[:200],
                'error_code': 'GARANTI_REFUND_FAIL',
            }

        except Exception as e:
            _logger.exception("Garanti iade hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'GARANTI_REFUND_ERROR',
            }

    def cancel(self, transaction_id, bank_order_id, auth_code,
               amount, currency, **kwargs):
        _logger.info(
            "Garanti iptal islemi: siparis=%s", bank_order_id,
        )
        try:
            url = self._get_api_url()
            terminal_id = self.credentials.get('terminalId', '')
            merchant_id = self.credentials.get('merchantId', '')
            prov_user_id = self.credentials.get('provUserPassword', '')

            amount_int = int(round(amount * 100))
            terminal_padded = terminal_id.zfill(9)
            security_data = self._generate_sha512(
                prov_user_id + terminal_padded
            )
            hash_data = (
                f"{bank_order_id}{terminal_id}{amount_int}{security_data}"
            )
            hash_value = self._generate_sha512(hash_data)

            xml_data = (
                f'<?xml version="1.0" encoding="UTF-8"?>'
                f'<GVPSRequest>'
                f'<Mode>{"TEST" if self.environment == "test" else "PROD"}</Mode>'
                f'<Version>v0.01</Version>'
                f'<Terminal>'
                f'<ProvUserID>PROVAUT</ProvUserID>'
                f'<HashData>{hash_value}</HashData>'
                f'<UserID>PROVAUT</UserID>'
                f'<ID>{terminal_id}</ID>'
                f'<MerchantID>{merchant_id}</MerchantID>'
                f'</Terminal>'
                f'<Order><OrderID>{bank_order_id}</OrderID></Order>'
                f'<Transaction>'
                f'<Type>void</Type>'
                f'<Amount>{amount_int}</Amount>'
                f'<CurrencyCode>{self._get_currency_code(currency)}</CurrencyCode>'
                f'</Transaction>'
                f'</GVPSRequest>'
            )

            result = self._make_request(
                url, data=xml_data,
                headers={'Content-Type': 'application/xml'},
                is_json=False,
            )

            resp_text = str(result.get('data', ''))
            if 'Approved' in resp_text or '<Code>00</Code>' in resp_text:
                return {
                    'success': True,
                    'response_code': '00',
                    'response_message': 'Iptal basarili',
                }
            return {
                'success': False,
                'error_message': resp_text[:200],
                'error_code': 'GARANTI_CANCEL_FAIL',
            }

        except Exception as e:
            _logger.exception("Garanti iptal hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'GARANTI_CANCEL_ERROR',
            }

    @staticmethod
    def _get_currency_code(currency):
        mapping = {'TRY': '949', 'USD': '840', 'EUR': '978'}
        return mapping.get(currency, '949')


# ═══════════════════════════════════════════════════════════════════════
#  Yapi Kredi (Posnet) Integration
# ═══════════════════════════════════════════════════════════════════════

class YapiKrediIntegration(BankIntegrationBase):
    """Yapi Kredi Posnet integration."""

    TEST_URL_3D = 'https://setmpos.ykb.com/3DSWebService/YKBPaymentService'
    PROD_URL_3D = 'https://posnet.yapikredi.com.tr/3DSWebService/YKBPaymentService'
    TEST_URL_API = 'https://setmpos.ykb.com/PosnetWebService/XML'
    PROD_URL_API = 'https://posnet.yapikredi.com.tr/PosnetWebService/XML'

    def _get_3d_url(self):
        return self.PROD_URL_3D if self.environment == 'production' else self.TEST_URL_3D

    def _get_api_url(self):
        return self.PROD_URL_API if self.environment == 'production' else self.TEST_URL_API

    def create_payment_form(self, amount, currency, installment_count,
                            order_id, transaction_id, success_url,
                            fail_url, callback_url, **kwargs):
        _logger.info(
            "Yapi Kredi (Posnet) odeme formu olusturuluyor: tutar=%.2f, taksit=%d",
            amount, installment_count,
        )
        try:
            merchant_id = self.credentials.get('merchantId', '')
            terminal_id = self.credentials.get('terminalId', '')
            posnet_id = self.credentials.get('posnetId', '')
            enc_key = self.credentials.get('encKey', '')

            amount_int = int(round(amount * 100))
            # Posnet requires order ID format: XXXXYYYYZZZ (exactly 20 chars)
            posnet_order_id = order_id.ljust(20, '0')[:20]

            # Generate MAC (Message Authentication Code)
            mac_str = f"{posnet_order_id};{amount_int};{currency};{merchant_id};{enc_key}"
            mac_value = self._generate_sha256(mac_str)

            form_data = {
                'mid': merchant_id,
                'tid': terminal_id,
                'posnetID': posnet_id,
                'posnetData': '',
                'posnetData2': '',
                'digest': mac_value,
                'vftCode': '000000' if installment_count <= 1 else '',
                'merchantReturnURL': callback_url,
                'url': '',
                'lang': 'tr',
                'orderID': posnet_order_id,
                'amount': str(amount_int),
                'currencyCode': self._get_currency_code(currency),
                'installmentCount': (
                    str(installment_count).zfill(2) if installment_count > 1 else '00'
                ),
                'ccno': kwargs.get('card_number', ''),
                'expDate': (
                    kwargs.get('card_exp_year', '')[-2:] +
                    kwargs.get('card_exp_month', '').zfill(2)
                ),
                'cvc': kwargs.get('card_cvv', ''),
            }

            html = QnbPayIntegration._build_auto_submit_form(
                self._get_3d_url(), form_data
            )
            return {
                'success': True,
                'html_form': html,
            }

        except Exception as e:
            _logger.exception("Yapi Kredi odeme formu hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'YKB_ERROR',
            }

    def process_3d_response(self, notification_data):
        _logger.info("Yapi Kredi (Posnet) 3D yaniti isleniyor...")
        try:
            approved = notification_data.get('approved', '')
            resp_code = notification_data.get('respCode', '')
            resp_text = notification_data.get('respText', '')
            order_id = notification_data.get('orderID', '')

            mac = notification_data.get('mac', '')
            xid = notification_data.get('xid', '')

            if approved == '1' or resp_code == '00':
                return {
                    'success': True,
                    'response_code': resp_code,
                    'response_message': resp_text,
                    'bank_order_id': order_id,
                    'auth_code': notification_data.get('authCode', ''),
                    'rrn': notification_data.get('hostlogkey', ''),
                    'host_ref_num': notification_data.get('hostlogkey', ''),
                    'md_status': '1',
                    'xid': xid,
                    'threed_status': 'success',
                }

            return {
                'success': False,
                'error_message': resp_text or 'Yapi Kredi odeme basarisiz',
                'error_code': resp_code,
                'response_code': resp_code,
                'response_message': resp_text,
                'bank_order_id': order_id,
            }

        except Exception as e:
            _logger.exception("Yapi Kredi 3D yanit hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'YKB_3D_ERROR',
            }

    def refund(self, transaction_id, bank_order_id, auth_code,
               amount, currency, **kwargs):
        _logger.info(
            "Yapi Kredi iade islemi: siparis=%s, tutar=%.2f",
            bank_order_id, amount,
        )
        try:
            url = self._get_api_url()
            merchant_id = self.credentials.get('merchantId', '')
            terminal_id = self.credentials.get('terminalId', '')

            amount_int = int(round(amount * 100))
            posnet_order_id = bank_order_id.ljust(20, '0')[:20]

            xml_data = (
                f'<?xml version="1.0" encoding="UTF-8"?>'
                f'<posnetRequest>'
                f'<mid>{merchant_id}</mid>'
                f'<tid>{terminal_id}</tid>'
                f'<return>'
                f'<amount>{amount_int}</amount>'
                f'<currencyCode>{self._get_currency_code(currency)}</currencyCode>'
                f'<orderID>{posnet_order_id}</orderID>'
                f'</return>'
                f'</posnetRequest>'
            )

            result = self._make_request(
                url, data=xml_data,
                headers={'Content-Type': 'application/xml'},
                is_json=False,
            )

            resp_text = str(result.get('data', ''))
            if '<approved>1</approved>' in resp_text:
                return {
                    'success': True,
                    'response_code': '00',
                    'response_message': 'Iade basarili',
                }
            return {
                'success': False,
                'error_message': resp_text[:200],
                'error_code': 'YKB_REFUND_FAIL',
            }

        except Exception as e:
            _logger.exception("Yapi Kredi iade hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'YKB_REFUND_ERROR',
            }

    def cancel(self, transaction_id, bank_order_id, auth_code,
               amount, currency, **kwargs):
        _logger.info(
            "Yapi Kredi iptal islemi: siparis=%s", bank_order_id,
        )
        try:
            url = self._get_api_url()
            merchant_id = self.credentials.get('merchantId', '')
            terminal_id = self.credentials.get('terminalId', '')

            amount_int = int(round(amount * 100))
            posnet_order_id = bank_order_id.ljust(20, '0')[:20]

            xml_data = (
                f'<?xml version="1.0" encoding="UTF-8"?>'
                f'<posnetRequest>'
                f'<mid>{merchant_id}</mid>'
                f'<tid>{terminal_id}</tid>'
                f'<reverse>'
                f'<transaction>sale</transaction>'
                f'<orderID>{posnet_order_id}</orderID>'
                f'<authCode>{auth_code}</authCode>'
                f'</reverse>'
                f'</posnetRequest>'
            )

            result = self._make_request(
                url, data=xml_data,
                headers={'Content-Type': 'application/xml'},
                is_json=False,
            )

            resp_text = str(result.get('data', ''))
            if '<approved>1</approved>' in resp_text:
                return {
                    'success': True,
                    'response_code': '00',
                    'response_message': 'Iptal basarili',
                }
            return {
                'success': False,
                'error_message': resp_text[:200],
                'error_code': 'YKB_CANCEL_FAIL',
            }

        except Exception as e:
            _logger.exception("Yapi Kredi iptal hatasi: %s", str(e))
            return {
                'success': False,
                'error_message': str(e),
                'error_code': 'YKB_CANCEL_ERROR',
            }

    @staticmethod
    def _get_currency_code(currency):
        mapping = {'TRY': 'TL', 'USD': 'US', 'EUR': 'EU'}
        return mapping.get(currency, 'TL')


# ═══════════════════════════════════════════════════════════════════════
#  Factory function
# ═══════════════════════════════════════════════════════════════════════

# Mapping of gateway codes to integration classes
_INTEGRATION_MAP = {
    'param': ParamIntegration,
    'tosla': ToslaIntegration,
    'iyzico': IyzicoIntegration,
    'qnbpay': QnbPayIntegration,
    'akbank_pos': AkbankIntegration,
    'estv3_pos': AkbankIntegration,       # EST v3 shares the same protocol
    'garanti_pos': GarantiIntegration,
    'posnet': YapiKrediIntegration,
    'payfor': QnbPayIntegration,          # PayFor uses similar protocol
    'payflex_mpi': QnbPayIntegration,     # PayFlex MPI uses similar protocol
    'interpos': QnbPayIntegration,        # InterPOS uses similar protocol
    'kuveyt_pos': GarantiIntegration,     # Kuveyt uses similar protocol
}


def get_bank_integration(gateway, bank=None):
    """Factory function: return the appropriate integration instance.

    :param gateway: turkish.pos.gateway recordset (singleton).
    :param bank:    turkish.pos.bank recordset (singleton) or None.
    :return: BankIntegrationBase subclass instance, or None.
    """
    if not gateway:
        _logger.warning("get_bank_integration: gateway parametresi bos.")
        return None

    code = gateway.code if hasattr(gateway, 'code') else str(gateway)
    cls = _INTEGRATION_MAP.get(code)

    if cls is None:
        _logger.error(
            "Desteklenmeyen gateway kodu: %s. Desteklenen kodlar: %s",
            code, ', '.join(_INTEGRATION_MAP.keys()),
        )
        return None

    _logger.debug(
        "Bank entegrasyonu olusturuluyor: gateway=%s, sinif=%s",
        code, cls.__name__,
    )
    return cls(gateway, bank)
