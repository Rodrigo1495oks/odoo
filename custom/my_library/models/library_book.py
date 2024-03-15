from odoo.exceptions import UserError

from odoo.tools.translate import _

from datetime import timedelta

from odoo import models, fields, api

from odoo.exceptions import ValidationError


class LibraryBook(models.Model):

    _name = 'library.book'
    _description = 'Libro de la Biblioteca'
    _order = 'date_release desc, name'
    _rec_name = 'short_name'
    _inherit = ['base.archive']
    isbn = fields.Char('Title')

    def name_get(self):
        result = []
        for book in self:
            authors = book.author_ids.mapped('name')
            name = '%s (%s)' % (book.name, ', '.join(authors))
            result.append((book.id, name))
            return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike',
                     limit=100, name_get_uid=None
                     ):
        
        if args is None:
            args = []
        else:
            args.copy()
        if not (name == '' and operator == 'ilike'):
            args += ['|', '|', ('name', operator, name),
                     ('isbn', operator, name),
                     ('author_ids.name', operator, name)
                     ]
        return super(LibraryBook, self)._name_search(
            name=name, args=args, operator=operator,
            limit=limit, name_get_uid=name_get_uid
        )

    class BaseArchive(models.AbstractModel):
        _name = 'base.archive'
        active = fields.Boolean(default=True)

        def do_archive(self):
            for record in self:
                record.active = not record.active

    # heredar del modelo abstracto en este mismo archivo

    name = fields.Char('Title', required=True)
    short_name = fields.Char(
        'Short Title', required=True, translate=True, index=True)

    notes = fields.Text("Internal Notes")
    state = fields.Selection(
        [('draft', 'Not Available'),
         ('available', 'Available'),
         ('lost', 'Lost'),
         ('borrowed', 'Borrowed')
         ],
        'State', default='draft', translate=True)

    def find_book(self):
        domain = [
            '|',
            '&', ('name', 'ilike', 'Book Name'),
            ('category_id.name', 'ilike', 'Category'),
            '&', ('name', 'ilike', 'Book Name 2'),
            ('category_id.name', 'ilike', 'Category Name 2')
        ]
        books = self.search(domain)
        print(books)

    def find_partner(self):
        PartnerObj = self.env['res.partner']
        domain = [
            '&', ('name', 'ilike', 'Parth Gajjar'),
            ('company_id.name', '=', 'Odoo')
        ]
        partner = PartnerObj.search(domain)

    @api.model
    def books_with_multiple_authors(self, all_books):
        def predicate(book):
            if len(book.author_ids) > 1:
                return True
            return False
        return all_books.filter(predicate)

    @api.model
    def get_author_names(self, books):
        return books.mapped('author_ids.name')

    @api.model
    def is_allowed_transition(self, old_state, new_state):
        allowed = [('draft', 'available'),
                   ('available', 'borrowed'),
                   ('borrowed', 'available'),
                   ('available', 'lost'),
                   ('borrowed', 'lost'),
                   ('lost', 'available')]
        return (old_state, new_state) in allowed

    def change_state(self, new_state):
        for book in self:
            if book.is_allowed_transition(book.state, new_state):
                book.state = new_state
            else:
                msg = _('Moving from %s to %s is not allowed') % (
                    book.state, new_state)
                raise UserError(msg)

    def make_available(self):
        self.change_state('available')

    def make_borrowed(self):
        self.change_state('borrowed')

    def make_lost(self):
        self.change_state('lost')

    description = fields.Html("Description", sanitize=True, strip_style=False,
                              translate=True, help='Escribe una descipcion para el libro')
    cover = fields.Binary(
        'Book Cover', help='carga aqui la portada para el libro')
    out_of_print = fields.Boolean('Out of Print?')
    # time_record = fields.Date.now("Hora de registro")
    date_release = fields.Date('Release Date')
    old_edition = fields.Many2one('library.book', string='Old Edition')

    def change_release_date(self):
        self.ensure_one()
        # se puede hacer: self.date_release=fields.Date.today()
        # o lo siguiente para actualizar varios campos a la vez
        self.update({
            'date_release': fields.Datetime.now(),
        })

    date_updated = fields.Datetime('Last Updated')
    pages = fields.Integer('Number of Pages',
                           groups='base.group_user',
                           states={'lost': [('readonly', True)]},
                           help='Total book page count', company_dependent=False)
    reader_rating = fields.Float(
        'Reader Average Rating',
        digits=(14, 4),  # Precision de decimales opcional
    )
    author_ids = fields.Many2many(
        'res.partner',
        string='Authors'
    )

    cost_price = fields.Float('Book Cost')  # , digits='Book Price')

    currency_id = fields.Many2one(
        'res.currency', string='Currency'
    )
    retail_price = fields.Monetary(
        'Retail Price',
        currency_field='currency_id',
    )
    publisher_id = fields.Many2one(
        'res.partner', string='Publisher',
        ondelete='set null',
        context={},
        domain=[],
    )
    publisher_city = fields.Char(
        'Publisher City',
        related='publisher_id.city',
        readonly=True,
    )

    # insertando el campo de jerarquia

    category_id = fields.Many2one('library.book.category', string='Categoría')
    # creando una restricción de campo SQL
    _sql_constraints = [
        ('name_uniq', 'UNIQUE (name)',
            'Book title must be unique.'),
        ('positive_page', 'CHECK(pages>0)',
            'No of pages must be positive')
    ]

    @api.model
    def _referencable_models(self):
        models = self.env['ir.model'].search([
            ('field_id.name', '=', 'message_ids')
        ])
        return [(x.model, x.name) for x in models]

    ref_doc_id = fields.Reference(
        selection='_referencable_models',
        string='Reference Document'
    )
    # creando una restricción de campo python

    def _check_release_date(self):
        for record in self:
            if record.date_release and record.date_release > fields.Date.today():
                raise models.ValidationError(
                    'Release date must be in the past'
                )

    def _search_age(self, operator, value):
        today = fields.Date.today()
        value_days = timedelta(days=value)
        value_date = today-value_days
        # convert the operator:
        # book with age>value have a date<value_date
        operator_map = {
            '>': '<', '>=': '<=',
            '<': '>', '<=':  '>=',
        }
        new_op = operator_map.get(operator, operator)
        return [('date_release', new_op, value_date)]

# creando un campo computado

    age_days = fields.Float(
        string='Days Since Release',
        compute='_compute_age',
        inverse='_inverse_age',
        search='_search_age',
        store=False,  # optional
        compute_sudo=True,  # optional
    )

    # la logica para computar el campo

    @api.depends('date_release')
    def _compute_age(self):
        today = fields.Date.today()
        for book in self:
            if book.date_release and book.date_release < today:
                delta = today - book.date_release
                book.age_days = delta.days
            else:
                book.age_days = 0

    def _inverse_age(self):
        today = fields.Date.today()
        for book in self.filtered('date_release'):
            d = today-timedelta(days=book.age_days)
            book.date_release = d

    manager_remarks = fields.Text('Manager Remarks')
    # restricciones de grupo de usuarios 
    is_public = fields.Boolean(groups='my_library.librarian_group_manager')
    private_notes = fields.Text(groups='my_library.librarian_group_manager')
    # agregando restricciones para que solo un grupo de usuarios pueda modificar el campo  manager remarks

    @api.model
    def create(self, values):
        if not self.user_has_groups('my_library.librarian_group_manager'):
            if 'manager_remarks' in values:
                raise UserError(
                    'You are not allowed to modify '
                    'manager remarks'
                )
        return super(LibraryBook, self).create(values)

    def write(self, values):
        if not self.user_has_groups('my_library.librarian'):
            if 'manager_remarks' in values:
                raise UserError('You are not allowed to modify '
                                'manager remarks')
        return super(LibraryBook, self).write(values)

    # metodo para actualizar el precio

    @api.model
    def _update_book_price(self):
        all_books = self.search([])
        for book in all_books:
            book.cost_price += 10

    @api.model
    def update_book_price(self, category, amount_to_increase):
        category_books = self.search(['category_id', '=', category.id])
        for book in category_books:
            book.cost_price+=amount_to_increase

# modificando el model de personas - res.partnert (herencia)


class ResPartner(models.Model):

    _inherit = 'res.partner'
    _order = 'name'
    published_books_ids = fields.One2many(
        'library.book', 'publisher_id',
        string='Published Books'
    )

    authored_book_ids = fields.Many2many(
        'library.book',
        string='Authored Books',
        relation='library_book_res_partner_rel'  # opcional

    )
    # herencia

    count_books = fields.Integer(
        'Number of authored Books',
        compute='_compute_count_books'
    )
    # metodo computado para calcular los libros publicados

    @api.depends('authored_book_ids')
    def _compute_count_books(self):
        for publish in self:
            publish.count_books = len(publish.authored_book_ids)

    # para conseguir el precio promedio de los libros
    @api.model
    def _get_average_cost(self):
        grouped_result = self.read_group(
            [('cost_price', '!=', False)],  # domain
            ['category_id', 'cost_price:avg'],  # Fields to access
            ['category_id']  # group_by
        )
        return grouped_result


def name_get(self):

    result = []

    for record in self:
        rec_name = "%s (%s)" % (record.name, record.date_release)
        result.append((record.id, rec_name))

    return result


class LibraryMember(models.Model):
    _name = 'library.member'
    _inherits = {'res.partner': 'partner_id'}

    _description = 'Library Member'

    partner_id = fields.Many2one('res.partner', ondelete='cascade', required=True)
    date_start = fields.Date('Member Since')
    date_end = fields.Date('Termination Date')
    member_number = fields.Char()
    date_of_birth = fields.Date('Date of birth')

    def log_all_library_members(self):
        # this is an empty recordset of model library.member
        library_member_model = self.env['library.member']
        all_members = library_member_model.search([])
        print("ALL MEMBERS: ", all_members)
        return True
