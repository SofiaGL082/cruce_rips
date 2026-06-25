import pandas as pd
import re
from pathlib import Path

def normalizar_columna(nombre):
    return str(nombre).strip().upper().replace(" ", "_")

def leer_excel_con_encabezado(path, hoja=0):
    crudo = pd.read_excel(path, sheet_name=hoja, header=None, dtype=object)

    fila_encabezado = None
    for i in range(min(30, len(crudo))):
        valores = [normalizar_columna(x) for x in crudo.iloc[i].tolist()]
        if "CLIENTE" in valores and "SALDO_CUOTA" in valores and "ORDENMV" in valores:
            fila_encabezado = i
            break

    if fila_encabezado is None:
        raise ValueError(
            "No encontré una fila de encabezados con CLIENTE, SALDO CUOTA Y OrdenMv."
        )
    
    df = crudo.iloc[fila_encabezado + 1:].copy().reset_index(drop=True)
    df.columns = crudo.iloc[fila_encabezado].astype(str).str.strip()
    df = df.dropna(how="all").reset_index(drop=True)
    return df

def buscar_columna(df, nombre_objetivo):
    objetivo = normalizar_columna(nombre_objetivo)
    for col in df.columns:
        if normalizar_columna(col) == objetivo:
            return col
    raise ValueError(f"No encontré la columna requerida: {nombre_objetivo}")

def convertir_saldo(valor):
    if pd.isna(valor):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip()
    texto = re.sub(r"[^0-9,.\-]", "", texto)

    if texto in ("", "-", ".", ","):
        return None

    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")

    try:
        return float(texto)
    except ValueError:
        return None

def normalizar_cliente(valor):
    if pd.isna(valor):
        return ""
    return str(valor).strip()

def normalizar_orden(valor):
    if pd.isna(valor):
        return ""
    texto = str(valor).strip().upper()
    return re.sub(r"A$", "", texto)

def crear_cruce(archivo_entrada, hoja=0):
    """
    Procesa un archivo Excel y genera un nuevo archivo
    con los cruces encontrados por CLIENTE, OrdenMv y SALDO CUOTA.
    """

    df = leer_excel_con_encabezado(archivo_entrada, hoja)
    ruta_entrada = Path(archivo_entrada)

    carpeta_resultados = Path("resultados")
    carpeta_resultados.mkdir(exist_ok=True)

    archivo_salida = (
        carpeta_resultados
        / f"Cruces_{ruta_entrada.stem}.xlsx"
    )

    col_cliente = buscar_columna(df, "CLIENTE")
    col_saldo = buscar_columna(df, "SALDO CUOTA")
    col_orden = buscar_columna(df, "OrdenMv")

    trabajo = df.copy()
    trabajo["__fila_original"] = range(1, len(trabajo) + 1)
    trabajo["__cliente"] = trabajo[col_cliente].apply(normalizar_cliente)
    trabajo["__saldo_num"] = pd.to_numeric(trabajo[col_saldo].apply(convertir_saldo), errors="coerce")
    trabajo["__saldo_abs"] = trabajo["__saldo_num"].abs().round(2)
    trabajo["__orden_base"] = trabajo[col_orden].apply(normalizar_orden)

    trabajo = trabajo[
        trabajo["__cliente"].ne("")
        & trabajo["__orden_base"].ne("")
        & trabajo["__saldo_num"].notna()
        & trabajo["__saldo_num"].ne(0)
    ].copy()

    filas_salida = []
    grupo_cruce = 1

    claves = ["__cliente", "__orden_base", "__saldo_abs"]
    for _, grupo in trabajo.groupby(claves, dropna=False, sort=False):
        positivos = grupo[grupo["__saldo_num"] > 0].sort_values("__fila_original")
        negativos = grupo[grupo["__saldo_num"] < 0].sort_values("__fila_original")

        pares = min(len(positivos), len(negativos))
        for i in range(pares):
            # Primero negativo y luego positivo, para que queden juntos.
            par = pd.concat([negativos.iloc[[i]], positivos.iloc[[i]]])
            par = par.copy()
            par["GrupoCruce"] = grupo_cruce
            par["OrdenMv_Base"] = par["__orden_base"]
            par["Saldo_Abs_Cruce"] = par["__saldo_abs"]
            filas_salida.append(par)
            grupo_cruce += 1
    
    if filas_salida:
        resultado = pd.concat(filas_salida, ignore_index=True)
        columnas_aux = [c for c in resultado.columns if c.startswith("__")]
        resultado = resultado.drop(columns=columnas_aux)
        control = ["GrupoCruce", "OrdenMv_Base", "Saldo_Abs_Cruce"]
        resultado = resultado[control + [c for c in resultado.columns if c not in control]]
    else:
        resultado = pd.DataFrame(
            columns=["GrupoCruce", "OrdenMv_Base", "Saldo_Abs_Cruce"] + list(df.columns)
        )
    
    with pd.ExcelWriter(archivo_salida, engine="openpyxl") as writer:
        resultado.to_excel(writer, sheet_name="Cruces", index=False)
        resumen = pd.DataFrame(
            {
                "Dato": ["Archivo procesado", "Filas originales", "Cruces encontrados", "Filas exportadas"],
                "Valor": [Path(archivo_entrada).name, len(df), len(resultado) // 2, len(resultado)],
            }
        )
        resumen.to_excel(writer, sheet_name="Resumen", index=False)

    return {
        "filas_originales": len(df),
        "cruces_encontrados": len(resultado) // 2,
        "filas_exportadas": len(resultado),
        "archivo_salida": str(archivo_salida),
    }