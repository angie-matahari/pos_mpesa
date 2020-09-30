odoo.define('pos_mpesa.screens', function (require) {
    var models = require('point_of_sale.models');
	var gui = require('point_of_sale.gui');
	var screens = require('point_of_sale.screens');
	var utils = require('web.utils');
	var round_pr = utils.round_precision;
	var round_di = utils.round_decimals;
	
	var core = require('web.core');
	var QWeb = core.qweb;
	var _t = core._t;
    var PaymentScreenWidget = screens.PaymentScreenWidget;
    
    PaymentScreenWidget.include({

        render_payment_terminal: function() {
            var self = this;
            var order = this.pos.get_order();
            if (!order) {
                return;
            }
    
            this.$el.find('.send_payment_request').click(function () {
                var cid = $(this).data('cid');
                // Other payment lines can not be reversed anymore
                order.get_paymentlines().forEach(function (line) {
                    line.can_be_reversed = false;
                });
    
                var line = self.pos.get_order().get_paymentline(cid);
                var payment_terminal = line.payment_method.payment_terminal;
                // TODO: If mpesa terminal clause, do the next two lines
                var phone = $("#phone").val(); // Capture phone number
                payment_terminal.set_phone(phone); // Set it to the payment terminal
                line.set_payment_status('waiting');
                self.render_paymentlines();
    
                payment_terminal.send_payment_request(cid).then(function (payment_successful) {
                    if (payment_successful) {
                        line.set_payment_status('done');
                        line.can_be_reversed = self.payment_interface.supports_reversals;
                        self.reset_input(); // in case somebody entered a tip the amount tendered should be updated
                        $('#phone').val(''); // Reset phone number textbox
                    } else {
                        line.set_payment_status('retry');
                    }
                }).finally(function () {
                    self.render_paymentlines();
                });
    
                self.render_paymentlines();
            });
            this.$el.find('.send_payment_cancel').click(function () {
                var cid = $(this).data('cid');
                var line = self.pos.get_order().get_paymentline($(this).data('cid'));
                var payment_terminal = line.payment_method.payment_terminal;
                line.set_payment_status('waitingCancel');
                self.render_paymentlines();
    
                payment_terminal.send_payment_cancel(self.pos.get_order(), cid).finally(function () {
                    line.set_payment_status('retry');
                    self.render_paymentlines();
                });
    
                self.render_paymentlines();
            });
            this.$el.find('.send_payment_reversal').click(function () {
                var cid = $(this).data('cid');
                var line = self.pos.get_order().get_paymentline($(this).data('cid'));
                var payment_terminal = line.payment_method.payment_terminal;
                line.set_payment_status('reversing');
                self.render_paymentlines();
    
                payment_terminal.send_payment_reversal(cid).then(function (reversal_successful) {
                    if (reversal_successful) {
                        line.set_amount(0);
                        line.set_payment_status('reversed');
                    } else {
                        line.can_be_reversed = false;
                        line.set_payment_status('done');
                    }
                    self.render_paymentlines();
                });
            });
    
            this.$el.find('.send_force_done').click(function () {
                var line = self.pos.get_order().get_paymentline($(this).data('cid'));
                var payment_terminal = line.payment_method.payment_terminal;
                line.set_payment_status('done');
                self.render_paymentlines();
            });
        },
    });
});