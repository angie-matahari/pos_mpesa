# -*- coding: utf-8 -*-
import json
import requests
import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class PosMpesaPayment(models.Model):
   
    _name = 'pos.mpesa.payment'
    _description = 'POS Mpesa Payments'

    # TODO: Add currency check here

    name = fields.Char(string='Name', default='New')
    # TODO: Add currency field, amount becomes monetary
    amount = fields.Integer(string='Amount')
    checkout_request_id = fields.Char(string='Checkout Request ID')
    receipt_number = fields.Char(string='Receipt No.')
    phone_number = fields.Char(string='Phone')
    partner_id = fields.Many2one('res.partner', string='Customer')
    payment_method_id = fields.Many2one('pos.payment.method', string='Payment Method')
    payment_date = fields.Datetime(string='Date', required=True, readonly=True, default=lambda self: fields.Datetime.now())

    @api.model
    def feedback(self, post):
        _logger.info(post)
        checkout_request_id = post.get('CheckoutRequestID')
        if not checkout_request_id:
            error_msg = _('Mpesa: received data with missing reference (%s)') % (checkout_request_id)
            _logger.info(error_msg)
            raise ValidationError(error_msg)

        tx = self.env['pos.mpesa.payment'].search([('checkout_request_id', '=', checkout_request_id)])

        if not tx or len(tx) > 1:
            error_msg = _('Mpesa: received data for CheckoutRequestID %s') % (checkout_request_id)
            if not tx:
                error_msg += _('; no order found')
            else:
                error_msg += _('; multiple order found')
            _logger.info(error_msg)
            raise ValidationError(error_msg)

        # TODO: Capture receipt_number
        # TODO: Create customer and assign to this payment
        tx.write({
            'receipt_number': 'RECEIPT'
        })
        # pass