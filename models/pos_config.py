# coding: utf-8
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


# FIXME: May not be necessary
class PosConfig(models.Model):
    _inherit = 'pos.config'

    adyen_use_mpesa = fields.Boolean('Use MPesa Payment Method')