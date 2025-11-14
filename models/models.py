# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime


class AccountMove(models.Model):
    _inherit = "account.move"

    picking_id = fields.Many2one("stock.picking", string="Remito")

    def create_picking(self):
        """Crea un remito (stock.picking) a partir de la factura.

        - Solo para facturas de cliente (move_type == 'out_invoice')
        - Solo si aún no tiene picking asociado
        """
        for move in self:
            # Solo facturas de cliente y sin remito aún
            if move.move_type != "out_invoice" or move.picking_id:
                continue

            # Tipo de operación de salida
            picking_type = self.env["stock.picking.type"].search(
                [
                    ("company_id", "=", move.company_id.id),
                    ("code", "=", "outgoing"),
                ],
                limit=1,
            )
            if not picking_type:
                raise ValidationError(
                    _("No tiene configurada la operación de entrega (picking_type) para la compañía %s.")
                    % move.company_id.display_name
                )

            # Ubicación de cliente
            location_dest = self.env["stock.location"].search(
                [
                    ("usage", "=", "customer"),
                    ("company_id", "in", [False, move.company_id.id]),
                ],
                limit=1,
            )
            if not location_dest:
                raise ValidationError(
                    _("No está configurada la ubicación de cliente para la compañía %s.")
                    % move.company_id.display_name
                )

            vals_picking = {
                "picking_type_id": picking_type.id,
                "scheduled_date": datetime.now(),
                "origin": move.name,
                "partner_id": move.partner_id.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": location_dest.id,
                "company_id": move.company_id.id,
            }
            picking = self.env["stock.picking"].create(vals_picking)
            move.picking_id = picking.id

            # Crear movimientos por cada línea de factura con producto
            invoice_lines = move.invoice_line_ids.filtered(
                lambda l: l.product_id and not l.display_type
            )
            for line in invoice_lines:
                vals_move = {
                    "picking_id": picking.id,
                    "product_id": line.product_id.id,
                    "name": line.name or line.product_id.display_name,
                    "product_uom_qty": line.quantity,
                    "product_uom": line.product_uom_id.id,
                    "location_id": picking_type.default_location_src_id.id,
                    "location_dest_id": location_dest.id,
                    "company_id": move.company_id.id,
                }
                self.env["stock.move"].create(vals_move)
