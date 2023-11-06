import datetime
import calendar
monthinteger = 4
month = datetime.date(1900, monthinteger, 1).strftime('%B')

print(month)

print(datetime.date(1995, 5, 23).strftime('%D'))

# Fuente: https://www.iteramos.com/pregunta/39037/obtener-el-nombre-del-mes-a-partir-del-numero
year = 1995
for i in range(1, 13, 3):
    start_date = datetime.date(year, i, 1)
    end_date = datetime.date(year, i+2, calendar.monthrange(year, i+2)[1])
    print(end_date.year)
    print(start_date.strftime('%m/%d/%Y'))
    print('-------------d-------------------')
    print(end_date.strftime('%d/%m/%Y'))

date1=datetime.datetime(1995,12,14)
date2=datetime.datetime(1995,12,1)
date=datetime.datetime(1995,12,10)
if date>=date2 and date<=date1:
    print(date)
