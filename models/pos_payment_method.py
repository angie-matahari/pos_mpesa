# -*- coding: utf-8 -*-
import json
import logging
import time
import base64
import re
import requests

from werkzeug import urls

from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError

from odoo import models, fields, api, _
from odoo.http import request
from odoo.exceptions import ValidationError
from odoo.addons.pos_mpesa.controllers.main import PosMpesaController

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
    def get_latest_mpesa_status(self, short_code, pass_key, customer_key, secrete_key, checkout_request_id, test_mode):
        '''
        '''
        values = {}
        
        url = 'https://api.safaricom.co.ke/mpesa/stkpushquery/v1/query' if not test_mode else 'https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query'
        time_stamp, password = self.get_timestamp_passkey(short_code, pass_key)
        values.update({
            "BusinessShortCode": short_code,
            "Password": password,
            "Timestamp": time_stamp,
            "CheckoutRequestID": checkout_request_id
        })
        headers = {
            'Authorization': 'Bearer %s' % self._mpesa_get_access_token(customer_key, secrete_key, test_mode)
            }
        resp = requests.post(url, json=values, headers=headers)
        resp = resp.json()

    @api.model
    def mpesa_stk_push(self, data, test_mode, secrete_key, customer_key, short_code, pass_key):
        url = 'https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest' if not test_mode else 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
        time_stamp, password = self.get_timestamp_passkey(short_code, pass_key)
        values = {
            "BusinessShortCode": short_code,
            "Password": password,
            "Timestamp": time_stamp,
            "PartyB": short_code,
            "CallBackURL": self.get_callback(),
            "TransactionType": 'CustomerPayBillOnline',
            "Amount": data['amount'],
            "PartyA": data['phone'] or '254701823543',
            "PhoneNumber": data['phone'] or '254701823543',
            "AccountReference": data['shop_name'],
            "TransactionDesc": data['order_id']
        }
        
        headers = {
            'Authorization': 'Bearer %s' % self._mpesa_get_access_token(customer_key, secrete_key, test_mode)
            }
        resp = requests.post(url, json=values, headers=headers)
        if not resp.ok: 
            try:
                resp.raise_for_status()
            except HTTPError:
                _logger.error(resp.text)
                mpesa_error = resp.json().get('errorMessage', {})
                error_msg = " " + (_("MPesa gave us the following info about the problem: '%s'") % mpesa_error)
                raise ValidationError(error_msg)
        
        _logger.info(resp.json())
        self.mpesa_create_transaction(values, resp.json())
        return resp.json()

    def get_timestamp_passkey(self, short_code, pass_key):
        time_stamp = str(time.strftime('%Y%m%d%H%M%S'))
        passkey = short_code + pass_key + time_stamp
        password = str(base64.b64encode(passkey.encode('utf-8')), 'utf-8')
        return time_stamp, password

    def get_callback(self):
        base_url = self.get_base_url()
        return urls.url_join(base_url, PosMpesaController._callback_url)

    def _mpesa_get_access_token(self, customer_key, secrete_key, test_mode):
        url = 'https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials' if not test_mode else 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
        response = requests.get(url, auth=HTTPBasicAuth(
                customer_key, secrete_key))
        json_data = json.loads(response.text)
        return json_data['access_token']

    def get_base_url(self):
        url = ''
        if request:
            url = request.httprequest.url_root
        return url or self.env['ir.config_parameter'].sudo().get_param('web.base.url')

    def mpesa_create_transaction(self, values, resp):
        self.env['pos.mpesa.payment'].sudo().create({
            'amount': values['Amount'],
            'checkout_request_id': resp.get('CheckoutRequestID'),
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