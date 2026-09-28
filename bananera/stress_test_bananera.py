import random
import pandas as pd
import duckdb as db

def generar_datos_bananera(n=10000):
    registros = []
    
    # Variantes de cómo la gente escribe (el caos real)
    palabras_revision = ['se revisaron', 'revision de cajas:', 'inspeccion de', 
                         'cajas revisadas', 'revisadas', 'se inspeccionaron']
    
    palabras_rechazo = ['rechazadas por sobremaduracion', 'rechazadas x golpes',
                        'rechazadas', 'cajas rechazadas', 'rechazo por calidad',
                        'ninguna rechazada']
    
    palabras_temp = ['temp de bodega', 'temp bodega:', 'temp', 'temperatura',
                     'temp de camara']
    
    problemas_temp = ['temperatura no registrada', 'sensor dañado', 'temp -5 grados']
    
    for i in range(n):
        lote = random.randint(100, 200)
        cajas = random.randint(200, 600)
        rechazadas = random.randint(0, int(cajas * 0.15))
        temp = round(random.uniform(12.5, 15.0), 1)
        
        # Elegir formato aleatorio
        formato = random.randint(1, 8)
        
        if formato == 1:
            texto = f"registro {i+1}: lote {lote} se revisaron {cajas} cajas, {rechazadas} rechazadas por sobremaduracion, temp {temp} grados"
        elif formato == 2:
            texto = f"Registro {i+1}: LOTE {lote} revision de cajas: {cajas}, rechazo por calidad {rechazadas} cajas, temp bodega: {temp}"
        elif formato == 3:
            texto = f"registro {i+1}: lote {lote}, inspeccion de {cajas} cajas, ninguna rechazada, temp de bodega {temp} grados"
            rechazadas = 0
        elif formato == 4:
            texto = f"registro {i+1}: lote {lote} - {cajas} cajas revisadas - {rechazadas} rechazadas - temp {temp}"
        elif formato == 5:
            texto = f"registro {i+1}: lote {lote} se revisaron {cajas} cajas {rechazadas} rechazadas temp {temp}"
        elif formato == 6:
            texto = f"registro {i+1}: LOTE{lote} se revisaron {cajas} cajas, {rechazadas} rechazadas x sobremaduracion, temperatura no registrada"
            temp = None
        elif formato == 7:
            texto = f"registro {i+1}: lote {lote} se inspeccionaron {cajas} cajas, {rechazadas} rechazadas, temp -{random.randint(1,10)} grados (sensor dañado)"
            temp = None
        else:
            texto = f"registro {i+1}: lote {lote} se revisaron {cajas} cajas, {rechazadas} rechazadas por golpes, temp de camara {temp}"
        
        registros.append({
            'texto': texto,
            'esperado_lote': lote,
            'esperado_cajas': cajas,
            'esperado_rechaz': rechazadas,
            'esperado_temp': temp
        })
    
    return registros

datos = generar_datos_bananera(50)

# Crear DataFrame con solo el texto (como llegaría en la vida real)
df_sucio = pd.DataFrame({'Field1': [d['texto'] for d in datos]})

# Crear DataFrame con los valores esperados (para comparar)
df_esperado = pd.DataFrame({
    'esperado_lote': [d['esperado_lote'] for d in datos],
    'esperado_cajas': [d['esperado_cajas'] for d in datos],
    'esperado_rechaz': [d['esperado_rechaz'] for d in datos],
    'esperado_temp': [d['esperado_temp'] for d in datos]
})

print("=== MUESTRA DE DATOS SUCIOS ===")
for i in range(5):
    print(f"  {datos[i]['texto']}")

# Registrar en DuckDB
con=db.connect()
con.register('df', df_sucio)

# Tu pipeline
resultado = r"""WITH data_raw AS (SELECT Field1 FROM df WHERE Field1 IS NOT NULL),
CTE_1 as(SELECT Field1,
try_cast(regexp_extract(lower(Field1),'registro.*?([0-9]+)',1)as integer)as registro,
try_cast(regexp_extract(lower(Field1),'lote.*?([0-9]+)',1)as integer)as lote,
regexp_replace(regexp_replace(lower(Field1),'registro.*?[0-9]+','x'),'lote.*?[0-9]+','x')as texto_limpio
FROM data_raw),
CTE_2 as(SELECT Field1, registro, lote,
coalesce(try_cast(regexp_extract(texto_limpio,'([0-9]+).{0,20}?revis',1)as integer),
try_cast(regexp_extract(texto_limpio,'([0-9]+).{0,20}?inspecc',1)as integer),
try_cast(regexp_extract(texto_limpio,'inspecc.{0,20}?([0-9]+)',1)as integer),
try_cast(regexp_extract(texto_limpio,'revis.{0,20}?([0-9]+)',1)as integer))as cajas_revisadas,
CASE 
    WHEN lower(Field1) LIKE '%ningun%rechaz%' THEN 0
    ELSE coalesce(
        try_cast(regexp_extract(texto_limpio,'([0-9]+)\s*rechaz',1)as integer),
        try_cast(regexp_extract(texto_limpio,'rechaz.{0,35}?([0-9]+)',1)as integer))
END as rechaz_extraido,
CASE
    WHEN regexp_matches(lower(Field1),'temperatura no registrada') THEN NULL
    WHEN regexp_matches(lower(Field1),'temp.*?-[0-9]+') THEN NULL
    ELSE try_cast(regexp_extract(lower(Field1),'temp.*?([0-9]+[.,]?[0-9]*)',1)as double)
END as temperatura
FROM CTE_1)
SELECT registro, lote, cajas_revisadas, rechaz_extraido, temperatura
FROM CTE_2
ORDER BY registro"""

df_resultado = con.sql(resultado).df()

# COMPARAR RESULTADOS
print("\n=== AUDITORIA DE RESULTADOS ===")
aciertos = 0
fallos = 0
detalles_fallos = []

for i in range(len(df_resultado)):
    ok = True
    errores = []
    
    if df_resultado.iloc[i]['lote'] != df_esperado.iloc[i]['esperado_lote']:
        ok = False
        errores.append(f"lote: got {df_resultado.iloc[i]['lote']} expected {df_esperado.iloc[i]['esperado_lote']}")
    
    esp_cajas = df_esperado.iloc[i]['esperado_cajas']
    got_cajas = df_resultado.iloc[i]['cajas_revisadas']
    if pd.isna(got_cajas) or int(got_cajas) != esp_cajas:
        ok = False
        errores.append(f"cajas: got {got_cajas} expected {esp_cajas}")
    
    esp_rechaz = df_esperado.iloc[i]['esperado_rechaz']
    got_rechaz = df_resultado.iloc[i]['rechaz_extraido']
    if pd.isna(got_rechaz) or int(got_rechaz) != esp_rechaz:
        ok = False
        errores.append(f"rechaz: got {got_rechaz} expected {esp_rechaz}")
    
    esp_temp = df_esperado.iloc[i]['esperado_temp']
    got_temp = df_resultado.iloc[i]['temperatura']
    # MAL:
# BIEN:
    if esp_temp is None or pd.isna(esp_temp):
        if not pd.isna(got_temp):
            ok = False
            errores.append(f"temp: got {got_temp} expected NULL")
    else:
        if pd.isna(got_temp) or abs(got_temp - esp_temp) > 0.01:
            ok = False
            errores.append(f"temp: got {got_temp} expected {esp_temp}")
    
    if ok:
        aciertos += 1
    else:
        fallos += 1
        detalles_fallos.append(f"  Fila {i}: {errores}")
        detalles_fallos.append(f"    Texto: {datos[i]['texto'][:80]}...")

total = aciertos + fallos
tasa = round(aciertos / total * 100, 1)

print(f"\n  ACIERTOS: {aciertos}/{total}")
print(f"  FALLOS:   {fallos}/{total}")
print(f"  TASA DE EXITO: {tasa}%")

if detalles_fallos:
    print(f"\n=== DETALLE DE FALLOS ===")
    for d in detalles_fallos:
        print(d)
