import pandas as pd
import duckdb as db

# ============ DATOS ============
envios = {
    'guia': ['G-101','G-102','G-103','G-104','G-105','G-105','G-106','G-107','G-108','G-109'],
    'camion': ['CAM-03','CAM-03','CAM-05','CAM-03','CAM-05','CAM-05','CAM-07','CAM-03','CAM-05','CAM-03'],
    'conductor': ['Ricardo Mendoza','Ricardo Mendoza','Pedro Villalba','Ricardo Mendoza','Pedro Villalba','Pedro Villalba','Juan Borja','Ricardo Mendoza','Pedro Villalba','Ricardo Mendoza'],
    'ruta': ['GYE-UIO','GYE - UIO','Guayaquil-Quito','GYE-UIO','GYE - UIO','GYE - UIO','GYE-UIO','GYE-UIO','GYE-UIO','GYE-UIO'],
    'fecha_salida': ['2026-07-28','2026-07-29','2026-07-29','2026-07-30','2026-07-30','2026-07-30','2026-07-31','2026-07-31','01/08/2026','2026-08-01'],
    'hora_salida': ['06:30','14:00','15:20','06:15','13:45','13:45','07:00','14:30','06:00','quince hrs'],
    'hora_llegada': ['14:15','23:30','02:10','13:50','22:00','22:00','14:30','00:15','13:45','01:20'],
    'cajas': [120, 95, 110, 130, 85, 85, 100, None, 105, 90],
    'estado_entrega': ['entregado','Entregado Tardio','tardio','entregado','ENTREGADO TARDIO','ENTREGADO TARDIO','entregado','TARDIO - DAÑADO','entregado','tardio'],
    'temp_camion': [4.2, 4.5, 7.8, 4.1, 8.2, 8.2, 3.9, -2.0, 4.0, 9.1]
}

mantenimiento = {
    'camion': ['CAM-03','CAM-05','CAM-07','CAM-09'],
    'ultimo_service': ['2026-06-15','2026-03-20','2026-07-28','2026-07-01'],
    'km_actuales': [185000, 220000, 45000, 92000],
    'estado_mecanico': ['regular','critico','bueno','bueno']
}

# ============ PANDAS: LIMPIEZA PREVIA ============
df = pd.DataFrame(envios)
df_mant = pd.DataFrame(mantenimiento)

df.columns = df.columns.str.strip()
caja_backup = df['cajas'].copy()

for col in df.select_dtypes(include='object').columns:
    df[col] = df[col].str.strip()

df['cajas'] = caja_backup

df_mant.columns = df_mant.columns.str.strip()
km_backup = df_mant['km_actuales'].copy()

for col in df_mant.select_dtypes(include='object').columns:
    df_mant[col] = df_mant[col].str.strip()

df_mant['km_actuales'] = km_backup

# ============ REGISTRO EN DUCKDB ============
con = db.connect()
con.register('envios_raw', df)
con.register('mantenimiento', df_mant)

# ============ PIPELINE DE LIMPIEZA ============
limpieza = r"""
WITH cte_estandarizar AS (
    SELECT 
        UPPER(guia) AS guia,
        UPPER(camion) AS camion,
        CASE
            WHEN regexp_matches(LOWER(conductor), 'r[\.,]?\s*?mendoza') THEN 'RICARDO MENDOZA'
            WHEN regexp_matches(LOWER(conductor), 'p[\.,]?\s*?villalba') THEN 'PEDRO VILLALBA'
            WHEN regexp_matches(LOWER(conductor), 'juan[\.,]?\s*?borja') THEN 'JUAN BORJA'
            ELSE NULLIF(UPPER(conductor), '')
        END AS conductor,
        CASE
            WHEN LOWER(ruta) LIKE '%guayaquil%quito%' THEN 'GYE-UIO'
            ELSE REPLACE(UPPER(ruta), ' - ', '-')
        END AS ruta,
        CASE 
            WHEN fecha_salida LIKE '%-%' THEN TRY_CAST(fecha_salida AS DATE)
            ELSE TRY_CAST(strptime(fecha_salida, '%d/%m/%Y') AS DATE)
        END AS fecha_salida,
        CASE 
            WHEN regexp_matches(hora_salida, '[0-9]{1,2}:[0-9]{2}')
            THEN TRY_CAST(hora_salida AS TIME)
            ELSE NULL
        END AS hora_salida,
        CASE 
            WHEN regexp_matches(hora_llegada, '[0-9]{1,2}:[0-9]{2}')
            THEN TRY_CAST(hora_llegada AS TIME)
            ELSE NULL
        END AS hora_llegada,
        TRY_CAST(cajas AS INTEGER) AS cajas,
        UPPER(estado_entrega) AS estado_entrega,
        CASE
            WHEN TRY_CAST(temp_camion AS DOUBLE) < 0 THEN NULL
            ELSE TRY_CAST(temp_camion AS DOUBLE)
        END AS temp_camion
    FROM envios_raw
),
cte_limpio AS (
    SELECT DISTINCT * FROM cte_estandarizar
)
SELECT * FROM cte_limpio ORDER BY guia
"""

df_limpio = con.sql(limpieza).df()
con.register('envios_limpios', df_limpio)

# ============ ANALISIS: JOIN CON MANTENIMIENTO ============
join_query = r"""
SELECT 
    e.camion,
    m.estado_mecanico,
    m.km_actuales,
    COUNT(*) AS total_envios,
    COUNT(CASE WHEN e.estado_entrega LIKE '%TARDIO%' THEN 1 END) AS tardios,
    ROUND(COUNT(CASE WHEN e.estado_entrega LIKE '%TARDIO%' THEN 1 END) * 100.0 / COUNT(*), 1) AS pct_tardios
FROM envios_limpios e
INNER JOIN mantenimiento m ON e.camion = m.camion
GROUP BY e.camion, m.estado_mecanico, m.km_actuales
ORDER BY pct_tardios DESC
"""

print("=== ANALISIS POR CAMION + MANTENIMIENTO ===")
print(con.sql(join_query).df())

# ============ ANALISIS: TENDENCIA POR CONDUCTOR ============
tendencia = r"""
SELECT 
    guia,
    conductor,
    cajas,
    estado_entrega,
    ROW_NUMBER() OVER(PARTITION BY conductor ORDER BY guia) AS envio_num,
    SUM(CASE WHEN estado_entrega LIKE '%TARDIO%' THEN 1 ELSE 0 END) 
        OVER(PARTITION BY conductor ORDER BY guia) AS tardios_acum,
    COUNT(*) OVER(PARTITION BY conductor ORDER BY guia) AS envios_acum,
    ROUND(
        SUM(CASE WHEN estado_entrega LIKE '%TARDIO%' THEN 1 ELSE 0 END) 
            OVER(PARTITION BY conductor ORDER BY guia) * 100.0
        / COUNT(*) OVER(PARTITION BY conductor ORDER BY guia)
    , 1) AS pct_acumulado,
    LAG(cajas) OVER(PARTITION BY conductor ORDER BY guia) AS cajas_anterior,
    AVG(cajas) OVER(PARTITION BY conductor ORDER BY guia) AS promedio_acum
FROM envios_limpios
WHERE conductor IS NOT NULL
"""

print("\n=== TENDENCIA POR CONDUCTOR ===")
print(con.sql(tendencia).df())
