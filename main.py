from flask_socketio import SocketIO, send, emit
from flask import Flask, render_template
import sys
from os import listdir, mkdir, remove
from os.path import isfile, join, splitext, isdir
import face_recognition
from shutil import copyfile, rmtree, move
import uuid
import pickle
from PIL import Image, ImageDraw, ImageFont
import json
import base64
from time import sleep
import re
from engineio.async_drivers import gevent

# Custom functions
from helpers import isImage, createModelsFolders, resize_img, cleanTempFiles
# Custom variables
from variables import temp_config_json, saved_config_json, face_distance_tolerance

# routes
from variables import temp_models_route, temp_box_route
from variables import saved_models_route, saved_box_route

# Si no existen, creo las carpetas necesarias
createModelsFolders()

modelOverlayFont = ImageFont.truetype('./poppins_font.ttf', 35)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'this is not a secret key!'
socketio = SocketIO(app, cors_allowed_origins="*")


def sendMsg(func, json):
    """
    Envio data al frontend
    """
    emit(func, json)


@socketio.on('connect')
def handle_connect():
    emit('connected', {'message': 'Connected to socket'})


@socketio.on("detect_face_model")
def detect_face_model(image_file):
    """
    Dada la ruta de una imagen, guarda temporalmente un modelo
    y la foto para luego decidir si se guarda o no.
    """
    # Reviso si es una imagen
    if not isImage(image_file):
        sendMsg("detect_face_model",
                {"error": "El archivo seleccionado no es una imagen."})
        return

    # Elimino archivos temporales
    cleanTempFiles()

    # Detecto caras en al foto
    img_load = face_recognition.load_image_file(image_file)
    face_locations = face_recognition.face_locations(img_load)
    face_encondings = face_recognition.face_encodings(
        img_load, face_locations)

    json_data = {
        "models": []
    }

    json_flush = []

    for (top, right, bottom, left), face_encoding in zip(face_locations, face_encondings):
        uid = str(uuid.uuid4())

        # Recorto la imagen
        pil_image = Image.fromarray(img_load)
        pil_image = pil_image.crop((left, top, right, bottom))
        pil_image = resize_img(pil_image)

        # Salvo modelo, y la imagen editada
        box_img_route = join(
            temp_box_route, "{}.png".format(uid))
        img_model = join(temp_models_route,
                         "{}.pkl".format(uid))

        # Guardo modelo
        with open(img_model, 'wb') as f:
            pickle.dump(face_encoding, f)

        # Guardo imagen original y con caja
        pil_image.save(box_img_route)

        json_data['models'].append({
            "file_path": image_file,
            "img_model": img_model,
            "box_img": box_img_route,
            "uuid": uid
        })

        json_flush.append({
            "uuid": uid,
            "img": box_img_route
        })

    if len(json_data['models']) > 0:
        # salvo json
        with open(temp_config_json, 'w') as outfile:
            json.dump(json_data, outfile, indent=4)

        sendMsg("detect_face_model", json_flush)
    else:
        sendMsg("detect_face_model", {
            "error": "No se encontraron rostros en la imagen seleccionada"
        })


@socketio.on("save_face_models")
def save_face_models(to_save_json):
    """
    Salva los modelos seleccionados de la lista de temporales
    """

    # Temporal config
    with open(temp_config_json, 'r') as f:
        temp_config = json.load(f)
    models = temp_config['models']

    # Current config
    with open(saved_config_json, 'r') as f:
        saved_config = json.load(f)

    # Si no encontre nada retorno
    if len(models) == 0:
        sendMsg("save_face_models", {
            "error": "No se encontraron rostros"
        })
        return

    to_save_list = []
    for x in models:
        if x['uuid'] in to_save_json['uuids']:
            # Agrego nombre seleccionado por el usuario
            x['name'] = to_save_json['names'][to_save_json['uuids'].index(
                x['uuid'])]
            to_save_list.append(x)

    # Si no selecciono ninguno entonces limpio
    if len(to_save_list) == 0:
        sendMsg("save_face_models", {
            "error": "No se seleccionaron fotos"
        })
        cleanTempFiles()
        return

    # Copio los archivos
    for x in to_save_list:
        new_model_route = join(saved_models_route, x['uuid']+".pkl")
        new_box_route = join(saved_box_route, x['uuid']+".png")

        move(x['img_model'], new_model_route)
        move(x['box_img'], new_box_route)

        # Agrego a la configuracion
        saved_config['models'].append({
            "img_model": new_model_route,
            "uuid": x['uuid'],
            "box_img": new_box_route,
            "name": x['name']
        })

    # Guardo config
    with open(saved_config_json, 'w') as outfile:
        json.dump(saved_config, outfile, indent=4)

    sendMsg("save_face_models", {
        "message": "Los rostros seleccionados fueron guardados",
        "new_models": saved_config
    })

    # Limpio la carpeta de temporales
    cleanTempFiles()


@socketio.on("copy_detected_faces")
def copy_detected_faces(config):
    """
    De una carpeta, copia todas las imagenes que tengan rostros
    entre los seleccionados,
    recibe un json con:
    - Rostros seleccionados
    - Ruta a la carpeta con grupo de imagenes
    - Ruta a la carpeta destino
    """
    faces = config['faces']
    dest_route = config['dest']
    origin_route = config['origin']

    dest_img_list = [f for f in listdir(
        origin_route) if isImage(join(origin_route, f))]

    # Reviso que hayan imagenes
    if len(dest_img_list) == 0:
        sendMsg("copy_detected_faces", {
            "error": "No se encontraron imagenes en la carpeta de origen"
        })
        return

    # Cargo los modelos de los rostros elegidos
    known_faces = []
    with open(saved_config_json, 'r') as f:
        saved_config = json.load(f)
    for x in faces:
        face_info = [
            record for record in saved_config['models'] if record['uuid'] == x]
        if len(face_info) != 1:
            continue

        face_info = face_info[0]

        # Cargo modelo
        with open(face_info['img_model'], 'rb') as f:
            face = pickle.load(f)
            known_faces.append(face)

    if len(known_faces) == 0:
        sendMsg({"error": "No se encontraron los rostros seleccionados"})
        return False

    # Empiezo a recorrer la carpeta
    found = 0

    sendMsg("copy_detected_faces", {
        "message": "Iniciando proceso...",
        "state": "Running"
    })

    for index, image in enumerate(dest_img_list):
        # Armo la ruta
        route = join(origin_route, image)

        # Creo modelo
        img_load = face_recognition.load_image_file(route)
        img_model = face_recognition.face_encodings(img_load)

        # Recorro los rostros de la foto actual
        if len(img_model) > 0:
            for unknown_face in img_model:
                # Comparo con imagenes conocidas
                face_distances = face_recognition.face_distance(
                    known_faces, unknown_face
                )
                # Reviso distancia menor a 0.5
                for i, face_distance in enumerate(face_distances):
                    if face_distance < face_distance_tolerance:
                        found += 1
                        dst_route = join(dest_route, image)
                        copyfile(route, dst_route)
                        sendMsg("copy_detected_faces", {
                            "message": "Encontrado rostro seleccionado en {}".format(image),
                            "state": "Running",
                            "img": dst_route
                        })

                        break

    sendMsg("copy_detected_faces", {
        "message": "{} encontrados, finalizado con éxito.".format(found),
        "state": "Finalized"
    })


@socketio.on("get_saved_configuration")
def get_saved_configuration():
    with open(saved_config_json, 'r') as f:
        saved_config = json.load(f)

    sendMsg("get_saved_configuration", saved_config)


@socketio.on("delete_face")
def delete_face(uuid):
    """
    Recibe un uuid y borra el rostro correspondiente
    """
    with open(saved_config_json, 'r') as f:
        saved_config = json.load(f)

    found = False
    final_models = []
    for model in saved_config['models']:
        if model['uuid'] == uuid:
            found = True
            remove(model['img_model'])
            remove(model['box_img'])
        else:
            final_models.append(model)

    # Guardo config
    with open(saved_config_json, 'w') as outfile:
        json.dump({"models": final_models}, outfile, indent=4)

    response = {
        "models": final_models,
        "message": "Eliminado con exito"
    }

    sendMsg("delete_face", response)


@socketio.on("edit_face_name")
def edit_face_name(new_config):
    """
    Recibe un uuid y un nombre en json, edita la configuracion
    que corresponda
    """
    with open(saved_config_json, 'r') as f:
        saved_config = json.load(f)

    final_models = []
    for model in saved_config['models']:
        if model['uuid'] == new_config['uuid']:
            model['name'] = new_config['name']

        final_models.append(model)

    # Guardo config
    with open(saved_config_json, 'w') as outfile:
        json.dump({"models": final_models}, outfile, indent=4)

    response = {
        "models": final_models,
        "message": "Actualizado con exito"
    }

    sendMsg("edit_face_name", response)


if __name__ == '__main__':
    socketio.run(app)
