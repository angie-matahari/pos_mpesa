# -*- coding: utf-8 -*-

import logging
import pprint

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

class PosMpesaController(http.Controller):

    @http.route(
        ['/payment/mpesa/callback/'], type='json', auth='none', methods=['POST'], 
        csrf=False)
    def mpesa_return(self, **post):

        checkout_request_id = post.get('CheckoutRequestID', None)
        merchant_request_id = post.get('MerchantRequestID', None)
        _logger.info('notification received from mpesa:\n%s', pprint.pformat(post))
        if checkout_request_id and merchant_request_id:
            pos_mpesa_payment = request.env['pos.mpesa.payment'].sudo().search([('checkout_request_id', '=', checkout_request_id)], limit=1)
            pos_mpesa_payment.sudo().feedback(post)
        
        return "Success"