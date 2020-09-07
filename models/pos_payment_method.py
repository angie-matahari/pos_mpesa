# -*- coding: utf-8 -*-
import json
import requests
import logging

from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    def _get_payment_terminal_selection(self):
        return super(PosPaymentMethod, self)._get_payment_terminal_selection() + [('adyen', 'Adyen')]

    # FIXME: We should list only enabled or test and mpesa type acquirers
    mpesa_pos_acquirer_id = fields.Many2one('payment_acquirer', string='Mpesa Acquirer')

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

    # FIXME: Use the tx_id
    @api.model
    def get_latest_mpesa_status(self, payment_method_id, reference):
        '''
        '''
        payment_method = self.sudo().browse(payment_method_id)
        tx = self.env['payment.transaction'].sudo().search([('reference', '=', reference)])
        # payment_method.adyen_latest_response
        # latest_response = json.loads(latest_response) if latest_response else False
        # payment_method.adyen_latest_response = ''  # avoid handling old responses multiple times

        return {
            'tx_status': tx.state,
            'tx_id': tx.id,
            'tx_ref': tx.reference,
        }

    @api.model
    def proxy_mpesa_request(self, data):
        # FIXME: Streamline how to get the reference
        # DEBUG: Add all imports
        # QUESTION: Does the payment know itself when called from client side? 
        reference_values = data['order_id']
        reference = self.env['payment.transaction']._compute_reference(values=reference_values) 
        values = {
            'acquirer_id': self.mpesa_pos_acquirer_id.id,
            'reference': reference,
            'amount': data['amount'],
            'currency_id': data['currency_id'],
            'mpesa_tx_phone': data['phone'],
            'mpesa_pos_tx': True,
            # FIXME: Actually get the id here + int()
            'pos_order_id': int(data['order_id']),
            'type': 'server2server',
            # 'return_url': return_url,
            # FIXME: Add a way for guys to relate a tx with a pos.order
        }
        tx = self.env['payment.transaction'].sudo().with_context(lang=None).create(values)
        # PaymentProcessing.add_payment_transaction(tx)
        try:
            tx.s2s_do_transaction()
            # secret = request.env['ir.config_parameter'].sudo().get_param('database.secret')
            # token_str = '%s%s%s' % (tx.id, tx.reference, tx.amount)
            # token = hmac.new(secret.encode('utf-8'), token_str.encode('utf-8'), hashlib.sha256).hexdigest()
            # tx.return_url = return_url or '/website_payment/confirm?tx_id=%d&access_token=%s' % (tx.id, token)
        except Exception as e:
            _logger.exception(e)
        return tx.state
        # return resp.json()

    @api.onchange('use_payment_terminal')
    def _onchange_use_payment_terminal(self):
        super(PosPaymentMethod, self)._onchange_use_payment_terminal()
        if self.use_payment_terminal != 'mpesa':
            self.mpesa_pos_acquirer_id = False
            