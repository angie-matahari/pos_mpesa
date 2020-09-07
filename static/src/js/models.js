odoo.define('pos_adyen.models', function (require) {
    var models = require('point_of_sale.models');
    var PaymentMpesa = require('pos_mpesa.payment');
    
    models.register_payment_method('mpesa', PaymentMpesa);
    // Not yet sure what other models and fields I should be handling
    models.load_fields('pos.payment.method', ['mpesa_pos_acquirer_id']);
    });
    