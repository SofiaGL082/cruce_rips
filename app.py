from flask import Flask, render_template, request, send_file
from pathlib import Path
from procesamiento import crear_cruce

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def inicio():

    resultado = None
    error = None

    if request.method == "POST":

        archivo = request.files["archivo"]
        hoja = request.form["hoja"]

        carpeta_uploads = Path("uploads")
        carpeta_uploads.mkdir(exist_ok=True)

        ruta_archivo = carpeta_uploads / archivo.filename

        archivo.save(ruta_archivo)

        try:
            hoja_procesar = int(hoja)
        except ValueError:
            hoja_procesar = hoja

        try:

            resultado = crear_cruce(
                str(ruta_archivo),
                hoja=hoja_procesar
            )

            app.config["ULTIMO_RESULTADO"] = resultado["archivo_salida"]

            ruta_archivo.unlink(missing_ok=True)

        except Exception as e:
            error = str(e)

    return render_template(
        "index.html",
        resultado=resultado,
        error=error
    )

@app.route("/descargar")
def descargar():

    ruta_archivo = Path(
        app.config["ULTIMO_RESULTADO"]
    )

    return send_file(
        ruta_archivo,
        as_attachment=True,
        download_name=ruta_archivo.name
    )

if __name__ == "__main__":
    app.run(debug=True)