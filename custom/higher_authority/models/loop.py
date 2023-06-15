

for i in range(10+1):
    print(f"Número: {i}")

lines = ['valido', 'valido', 'valido', 'valido', 'valido']


def check_and_break(line):
    return line == 'valido'


if all([check_and_break(line) for line in lines]):
    print('verdadero')
else:
    print('falso')
