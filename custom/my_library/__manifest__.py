{
    'name': "My library",
    'summary': "Manage books easily",
    'description': """ 
         Manage Library
         ==============
         Description related to library.
     """,
    'author': "Rodrigo, Olivia",
    'website': "http://www.example.com",
    'category': 'Books',
    'version': '14.0.1',
    'depends': ['base'],
    'data': [
        # 'data/data.xml',
        'security/groups.xml',
        'security/ir.model.access.csv',
        'views/library_book.xml',
        'views/library_book_categ.xml',
        'views/library_book_members.xml',
    ],                                          
    # 'demo': ['demo.xml'],
    'licence': 'LGPL-3',
    'application': True,
    'auto_install': False,
    'installable': True,
    'external_dependencies': '',
}