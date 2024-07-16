from datetime import  datetime, date, timedelta, time
#
# print(sum([1,2,3]+[2,3,4]))
#
#
#
# date1=datetime.now()
# date2=datetime.now() - timedelta(days=90)
# date3=datetime.now() - timedelta(days=100)
# date4=datetime.now() - timedelta(days=120)
#
#
#
# print(max(date1,date2, date3,date4))
# print(min(date1,date2, date3,date4))

import operator

mi_diccionario = {"a": 10, "b": 20, "c": 15}
clave_maxima = max(mi_diccionario.items(), key=operator.itemgetter(1))[0]

print(f"La clave con el valor máximo es: {clave_maxima}")

tupla_de_valores=(datetime.now(), 1200)

print(tupla_de_valores[1:])