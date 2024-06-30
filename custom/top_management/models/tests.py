
# from odoo.tools import groupby

topics_ids=[{'id': 10, 'short_name': 'TP00010AM', 'name': 'Tema de reunion 1', 'description': 'desc', 'topic_type': 'issuance', 'num_votes_plus': 3546}, {'id': 9, 'short_name': 'TP00009AM', 'name': 'Tema de reunion 1', 'description': 'desc', 'topic_type': 'issuance', 'num_votes_plus': 4696}, {'id': 8, 'short_name': 'TP00008AM', 'name': 'Tema de reunion 1', 'description': 'desc', 'topic_type': 'issuance', 'num_votes_plus': 4697}, {'id': 20, 'short_name': 'TP00020AM', 'name': 'fghgfhgffg', 'description': 'fghgfgffghfhgh', 'topic_type': 'issuance', 'num_votes_plus': 6667}]

issuance_values=0

for topic in topics_ids:
    if topic['topic_type']=='issuance':
        issuance_values+=topic.get('num_votes_plus')

print(issuance_values)

lista=['name','short_name','']

lista_De_dicc=topics_ids=[{'id': 10, 'short_name': 'TP00010AM', 'name': 'Tema de reunion 1', 'description': 'desc', 'topic_type': 'issuance', 'num_votes_plus': 3546}, {'id': 9, 'short_name': 'TP00009AM', 'name': 'Tema de reunion 1', 'description': 'desc', 'topic_type': 'issuance', 'num_votes_plus': 4696}, {'id': 8, 'short_name': 'TP00008AM', 'name': 'Tema de reunion 1', 'description': 'desc', 'topic_type': 'issuance', 'num_votes_plus': 4697}, {'id': 20, 'short_name': 'TP00020AM', 'name': 'fghgfhgffg', 'description': 'fghgfgffghfhgh', 'topic_type': 'issuance', 'num_votes_plus': 6667}]
votos_issuance=sum([diccionario['num_votes_plus'] for diccionario in lista_De_dicc if diccionario['topic_type']=='issuance'])


print(votos_issuance)


print(sum([]))

print("diccionarios-----------------")
dictionary={"cadena":[], 1:[("asd",15)],2:[("ass",154)],3:[('item',1)],4:[('item',2)],5:[('item',3)]}
domain='cadena'
dictionary[domain].append(('item_nuevo',54))
print(dictionary.items())
print(dictionary.keys())


for key, item in dictionary.items():
    print(key, item)
    clave, valor = zip(*item)
    print(clave, valor)

lista=[(1,"item1"),(2,"item2"),(3,"item3")]
# nueva_dict=groupby(lista, key=1)



valores=False and True
print(valores)

valores=0 and 1

print(valores)

