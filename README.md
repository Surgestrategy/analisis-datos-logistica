# Análisis de Datos - Logística y Operaciones

Portafolio de proyectos de limpieza, transformación y análisis de datos 
aplicados a logística, producción y operaciones en Ecuador.

**Herramientas:** Python, pandas, DuckDB, SQL, regex

## Proyectos

### 1. Camaronera - Pipeline de Limpieza
- Pérdida detectada: $293,850 (camarón + balanceado)
- Pipeline de 10,000 registros con 100% de aciertos
- Técnicas: regex, CTEs, enmascaramiento en cascada, stress test

### 2. Bananera - Extracción de Texto Libre
- Pérdida detectada: $1,331.20 (diferencial + flete)
- Extracción de datos de notas de texto libre
- Técnicas: regexp_extract, cerca perezosa, COALESCE

### 3. Distribuidora - Análisis de Retrasos
- Pérdida detectada: $1,050 (penalizaciones + producto dañado)
- Hallazgo: 100% de retrasos son envíos de la tarde
- Técnicas: JOINs, Window Functions, porcentaje acumulado

### 4. Bodega Central - Caso de Estrés
- 13 filas con 8 tipos de suciedad, 3 proveedores
- 7 preguntas de negocio resueltas con GROUP BY
- Técnicas: HAVING, SUM(CASE WHEN), regex, TRY_CAST

## Contacto
Cristhoper García Pérez - QUITO Ecuador
garciacristhoper02@gmail.com
