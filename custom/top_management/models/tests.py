topics_ids=[{'id': 10, 'short_name': 'TP00010AM', 'name': 'Tema de reunion 1', 'description': 'desc', 'topic_type': 'issuance', 'num_votes_plus': 3546}, {'id': 9, 'short_name': 'TP00009AM', 'name': 'Tema de reunion 1', 'description': 'desc', 'topic_type': 'issuance', 'num_votes_plus': 4696}, {'id': 8, 'short_name': 'TP00008AM', 'name': 'Tema de reunion 1', 'description': 'desc', 'topic_type': 'issuance', 'num_votes_plus': 4697}, {'id': 20, 'short_name': 'TP00020AM', 'name': 'fghgfhgffg', 'description': 'fghgfgffghfhgh', 'topic_type': 'issuance', 'num_votes_plus': 6667}]

issuance_values=0

for topic in topics_ids:
    if topic['topic_type']=='issuance':
        issuance_values+=topic.get('num_votes_plus')

print(issuance_values)

lista=['name','short_name','']