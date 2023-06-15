
diccionario = {
    'method1': {
        'mode': 'unique',
        'name': 'metodo1'
    },
    'method2': {
        'mode': 'notunique',
        'name': 'metodo1'
    },
    'method3': {
        'mode': 'unique',
        'name': 'metodo1'
    }
}

unique_pay_methods = [
    k for k, v in diccionario.items() if v['mode'] == 'unique']

print(unique_pay_methods)


read_codes = [
    {'code':1234},
    {'code':3548},
    {'code':1222},
    {'code':1254},
]

all_journal_codes = {code_data['code'] for code_data in read_codes}

print(all_journal_codes)
journal_type='bank'
journal_code_base = (journal_type == 'cash' and 'CSH' or 'BNK')

print(journal_code_base)


print({}.get('code'))


lista_de_tuplas=[
    ('account','in','domain'),
    ('account','in','domain'),
    ('account','in','domain'),
    ('account','in','domain'),
]


print([item[0] for item in lista_de_tuplas])

print({"item1":'value1','item2':'value2'}.items())

