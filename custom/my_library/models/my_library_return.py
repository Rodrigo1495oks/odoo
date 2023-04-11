from odoo.exceptions import UserError

from odoo.tools.translate import _

from datetime import timedelta

from odoo import models, fields, api, exceptions


from odoo.exceptions import ValidationError

class LibraryBook(models.Model):
    _inherit='library.book'

    date_return=fields.Date('Date to return')

    def make_borrowed(self):
        day_to_borrow=self.category_id.max_borrow_days or 10
        self.date_return=fields.Date.today() + timedelta
        return super(LibraryBook, self).make_borrowed()

    def make_available(self):
        self.date_return=False
        return super(LibraryBook, self).make_available()

class LibraryBookCategory(models.Model):
    _inherit='library.book.category'

    max_borrow_days=fields.Integer(
        'Maximum borrow days',
        help="For how many days can be borrowed",
        default=10
    )
