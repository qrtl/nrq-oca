# -*- coding: utf-8 -*-
# Copyright 2016 Trobz
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging

from odoo import api, models, fields, _
from odoo.exceptions import Warning as UserError

_logger = logging.getLogger(__name__)


class PublicHolidaysNextYearWizard(models.TransientModel):
    _name = 'public.holidays.next.year.wizard'
    _description = 'Creates public holidays from existing ones'

    template_ids = fields.Many2many(
        comodel_name='hr.holidays.public',
        string='Templates',
        help='Select the public holidays to use as template. '
        'If not set, latest public holidays of each country will be used. '
        'Only the last templates of each country for each year will '
        'be taken into account (If you select templates from 2012 and 2015, '
        'only the templates from 2015 will be taken into account.',)
    year = fields.Integer(
        help='Year for which you want to create the public holidays. '
        'By default, the year following the template.',
    )
    public_holidays_next_year_day_ids = fields.One2many(
        comodel_name='public.holidays.next.year.day.wiz',
        inverse_name='public_holidays_next_year_wizard_id',
        string='Next year public holidays to create',
        help="Define next year's holiday dates",
    )

    @api.onchange('template_ids', 'year')
    def onchange_year_template_ids(self):
        self.ensure_one()
        self.public_holidays_next_year_day_ids = False
        for template in self.template_ids:
            for line in template.line_ids:
                last_date = fields.Date.from_string(line.date)
                new_year = self.year or template.year + 1
                new_day = self.env[
                    'public.holidays.next.year.day.wiz'].new({
                        'public_holidays_next_year_wizard_id': self.id,
                        'template_id': template.id,
                        'name': line.name,
                        'variable': line.variable,
                        'last_date': line.date,
                        'next_date': last_date.replace(year=new_year),
                    })
                self.public_holidays_next_year_day_ids |= new_day

    @api.multi
    def create_public_holidays(self):

        self.ensure_one()

        last_ph_dict = {}

        ph_env = self.env['hr.holidays.public']
        pholidays = self.template_ids or ph_env.search([])

        if not pholidays:
            raise UserError(_(
                'No Public Holidays found as template. '
                'Please create the first Public Holidays manually.'))

        for ph in pholidays:

            last_ph_country = last_ph_dict.get(ph.country_id, False)

            if last_ph_country:
                if last_ph_country.year < ph.year:
                    last_ph_dict[ph.country_id] = ph
            else:
                last_ph_dict[ph.country_id] = ph

        all_new_ph_values = []

        for last_ph in last_ph_dict.itervalues():

            new_year = self.year or last_ph.year + 1

            new_ph_vals = last_ph.copy_data({
                'year': new_year,
            })[0]

            line_values = []

            for last_ph_line in last_ph.line_ids:
                ph_line_date = fields.Date.from_string(last_ph_line.date)

                feb_29 = (
                    ph_line_date.month == 2 and
                    ph_line_date.day == 29)

                if feb_29:
                    # Handling this rare case would mean quite a lot of
                    # complexity because previous or next day might also be a
                    # public holiday.
                    raise UserError(_(
                        'You cannot use as template the public holidays '
                        'of a year that '
                        'includes public holidays on 29th of February '
                        '(2016, 2020...), please select a template from '
                        'another year.'))
                # If options were used to define next years public holidays
                # we look for a matching day
                if self.public_holidays_next_year_day_ids:
                    matching = self.public_holidays_next_year_day_ids.filtered(
                        lambda l: l.last_date == last_ph_line.date)
                    # If no match is found, it means the user did delete this
                    # day so we don't want to create it
                    if not matching:
                        continue
                    else:
                        new_date = matching.next_date
                # If options were not used, keep std behaviour
                else:
                    new_date = ph_line_date.replace(year=new_year)

                new_line_vals = last_ph_line.copy_data({
                    'date': new_date,
                })[0]
                new_line_vals.pop('year_id')
                line_values.append((0, 0, new_line_vals))

            new_ph_vals['line_ids'] = line_values
            all_new_ph_values.append(new_ph_vals)

        new_ph_ids = []
        for new_ph_to_create in all_new_ph_values:
            new_ph = ph_env.create(new_ph_to_create)
            new_ph_ids.append(new_ph.id)

        domain = [['id', 'in', new_ph_ids]]

        action = {
            'type': 'ir.actions.act_window',
            'name': 'New public holidays',
            'view_mode': 'tree,form',
            'res_model': 'hr.holidays.public',
            'domain': domain
        }

        return action


class HrHolidaysPublicLineVariable(models.TransientModel):

    _name = 'public.holidays.next.year.day.wiz'

    public_holidays_next_year_wizard_id = fields.Many2one(
        'public.holidays.next.year.wizard',
        readonly=True,
    )
    template_id = fields.Many2one(
        'hr.holidays.public',
        string='Template',
        required=True,
        readonly=True,
    )
    name = fields.Char(
        required=True,
        readonly=True,
    )
    last_date = fields.Date(
        required=True,
        readonly=True,
    )
    variable = fields.Boolean(
        readonly=True,
    )
    next_date = fields.Date(
        required=True,
    )
