def VAN(tasa,flujos):
  VA=0
  for j in range(len(flujos)):
    VA+=flujos[j]/(1+tasa)**j
  return VA

#print('VAN=',VAN(0.05,[-4000,1400,1300,1200,1100]))

def TIR(flujos):
  ka=-.5 #tasa de descuento inferior. Inicialmente -50%
  kc=10 #tasa de descuento superior. Inicialmente 1000%
  inf=VAN(ka,flujos) #VAN calculado con la tasa inferior
  sup=VAN(kc,flujos) #VAN calculado con la tasa superior
  if inf>=0 and sup<0:
    error=abs(inf-sup)
    while error>=1e-10:
      kb=(ka+kc)/2
      #print(kb)
      med=VAN(kb,flujos)
      if med<=0:
        kc=kb
      elif med>0:
        ka=kb
      inf=VAN(ka,flujos)
      sup=VAN(kc,flujos)
      error=inf-sup
    return kb
  else:
    return "sin TIR"

misFlujos1=[-4000,1400,1300,1200,1100]
misFlujos2=[-5000,1500,1600,1700,1800,1900]
misFlujos3=[-24375,1250, 31250]
misFlujos4=[-10000,3500,3500,3500]

print(TIR(misFlujos4))

print('TIR=',str(round(TIR(misFlujos3)*100,8))+'%')
