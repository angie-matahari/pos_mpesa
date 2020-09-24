# -*- coding: utf-8 -*-
import json
import logging
import time
import base64
import re
import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    def _get_payment_terminal_selection(self):
        return super(PosPaymentMethod, self)._get_payment_terminal_selection() + [('mpesa', 'Mpesa')]

    # TODO: Add phone number check
    # TODO: Add currency exchange on amount
    mpesa_secrete_key = fields.Char("Secret key", required_if_provider="mpesa")
    mpesa_customer_key = fields.Char("Customer key", 
                                    required_if_provider="mpesa")
    mpesa_short_code = fields.Char("Shortcode", required_if_provider="mpesa")
    mpesa_pass_key = fields.Char("Pass key", required_if_provider="mpesa")
    mpesa_test_mode = fields.Boolean(help='Run transactions in the test environment.', default=True)

    @api.constrains('mpesa_pos_acquirer_id')
    def _check_mpesa_terminal_identifier(self):
        for payment_method in self:
            if not payment_method.mpesa_pos_acquirer_id:
                continue
            existing_payment_method = self.search([('id', '!=', payment_method.id),
                                                   ('mpesa_pos_acquirer_id', '=', payment_method.mpesa_pos_acquirer_id)],
                                                  limit=1)
            if existing_payment_method:
                raise ValidationError(_('Terminal %s is already used on payment method %s.')
                                      % (payment_method.mpesa_pos_acquirer_id, existing_payment_method.display_name))

    # FIXME: Do we know exactly which payment_method_id we want
    @api.model
    def get_latest_mpesa_status(self, payment_method_id, short_code, passkey, checkout_request_id):
        '''
        '''
        values = {}
        time_stamp = str(time.strftime('%Y%m%d%H%M%S'))
        _logger.info(type(time_stamp))
        _logger.info(type(self.mpesa_short_code))
        _logger.info(type(self.mpesa_pass_key))
        passkey = self.mpesa_short_code + self.mpesa_pass_key + time_stamp
        password = str(base64.b64encode(passkey.encode('utf-8')), 'utf-8')
        url = 'https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query'

        values.update({
            "BusinessShortCode": self.mpesa_short_code,
            "Password": password,
            "Timestamp": time_stamp,
            "CheckoutRequestID": checkout_request_id
        })
        
        return self.mpesa_api_call(url, values)

    @api.model
    def mpesa_stk_push(self, data, test_mode, secrete_key, customer_key, short_code, pass_key):
        url = 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
        time_stamp = str(time.strftime('%Y%m%d%H%M%S'))
        passkey = short_code + pass_key + time_stamp
        password = str(base64.b64encode(passkey.encode('utf-8')), 'utf-8')
        callback = ''
        values = {
            "BusinessShortCode": self.mpesa_short_code,
            "Password": password,
            "Timestamp": time_stamp,
            "PartyB": self.mpesa_short_code,
            "CallBackURL": callback,
            "TransactionType": 'CustomerPayBillOnline',
            "Amount": data['amount'],
            "PartyA": data['phone'] or '254701823543',
            "PhoneNumber": data['phone'] or '254701823543',
            "AccountReference": data['shop_name'],
            "TransactionDesc": data['order_id']
        }
        
        resp = self.mpesa_api_call(url, values)
        if not resp.ok: 
            try:
                resp.raise_for_status()
            except HTTPError:
                _logger.error(resp.text)
                mpesa_error = resp.json().get('errorMessage', {})
                error_msg = " " + (_("MPesa gave us the following info about the problem: '%s'") % mpesa_error)
                raise ValidationError(error_msg)
        
        self.mpesa_create_transaction(values, resp)
        return resp.json()

    def mpesa_api_call(self, url, values={}, auth=False):
        # self.ensure_one()
        
        if auth:
            response = requests.get(url, auth=HTTPBasicAuth(
                self.mpesa_customer_key, self.mpesa_secrete_key))
            json_data = json.loads(response.text)
            return json_data['access_token']
        headers = {
            'Authorization': 'Bearer %s' % self._mpesa_get_access_token()
            }
        resp = requests.post(url, json=values, headers=headers)

        return resp.json()

    def _mpesa_get_access_token(self):
        url = 'https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
        return self.mpesa_request(url, auth=True)

    def get_base_url(self):
        self.ensure_one()
        # priority is always given to url_root
        # from the request
        url = ''
        if requests:
            url = requests.httprequest.url_root

        if not url and 'website_id' in self and self.website_id:
            url = self.website_id._get_http_domain()

        return url or self.env['ir.config_parameter'].sudo().get_param('web.base.url')

    def mpesa_create_transaction(self, values, resp):
        self.env['pos.mpesa.payment'].sudo().create({
            'amount': values['Amount'],
            'checkout_request_id': resp['CheckoutRequestID'],
            'phone_number': values['PartyA'],
            'payment_method_id': self,
        })

    @api.onchange('use_payment_terminal')
    def _onchange_use_payment_terminal(self):
        super(PosPaymentMethod, self)._onchange_use_payment_terminal()
        if self.use_payment_terminal != 'mpesa':
            self.mpesa_pos_acquirer_id = False
            

class PosPayment(models.Model):

    _inherit = 'pos.payment'

    mpesa_receipt = fields.Char(string='Mpesa Receipt No.')