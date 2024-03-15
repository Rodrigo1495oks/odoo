partner_ids=[{'name':'nombre1','shares':[{'codigo':'155ff','num_votes':100},{'codigo':'ff64536','num_votes':300},{'codigo':'ffyr6445','num_votes':200}]},{'nombre':'nombre2','shares':[{'codigo':'155ff','num_votes':100},{'codigo':'ff64536','num_votes':300},{'codigo':'ffyr6445','num_votes':200}]}]





# present_votes=sum([share['num_votes'] for share in [partner['shares'] for partner in partner_ids]])

# print(present_votes)

nueva_lista=[partner['shares'] for partner in partner_ids]
votos_presentes=0
for shares in nueva_lista:
    for share in shares:
        votos_presentes+=share['num_votes']

# print(votos_presentes)


vote=0

if vote:
    print('mayor a cero')
else:
    print('Es cero')