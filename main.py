import sys
from os import listdir, mkdir
from os.path import isfile, join, splitext, isdir
import face_recognition
from shutil import copyfile, rmtree, move
import uuid
import pickle
from PIL import Image, ImageDraw, ImageFont
import json
import base64
import re

# Custom functions
from helpers import isImage, createModelsFolders, imgToB64, cleanTempFiles, sendMsg
# Custom variables
from variables import temp_config_json, saved_config_json, face_distance_tolerance

# routes
from variables import temp_originals_route, temp_models_route, temp_box_route
from variables import saved_originals_route, saved_models_route, saved_box_route

# Si no existen, creo las carpetas necesarias
createModelsFolders()

modelOverlayFont = ImageFont.truetype('./poppins_font.ttf', 35)


class AppHandler:
    def detect_face_model(self):
        """
        Dada la ruta de una imagen, guarda temporalmente un modelo
        y la foto para luego decidir si se guarda o no.
        """
        image_file = sys.argv[2]
        # Reviso si es una imagen
        if not isImage(image_file):
            sendMsg({"error": "El archivo seleccionado no es una imagen."})
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

            pil_image = Image.fromarray(img_load)
            draw = ImageDraw.Draw(pil_image)
            # Draw box
            draw.rectangle(((left, top), (right, bottom)),
                           outline=(255, 0, 0), width=5)

            # Salvo modelo, imagen original y editada
            original_img_route = join(
                temp_originals_route, "{}.png".format(uid))
            box_img_route = join(
                temp_box_route, "{}.png".format(uid))
            img_model = join(temp_models_route,
                             "{}.pkl".format(uid))

            # Guardo modelo
            with open(img_model, 'wb') as f:
                pickle.dump(face_encoding, f)

            # Guardo imagen original y con caja
            pil_image.save(box_img_route)
            Image.fromarray(img_load).save(original_img_route)

            json_data['models'].append({
                "file_path": image_file,
                "original_img": original_img_route,
                "img_model": img_model,
                "box_img": box_img_route,
                "uuid": uid
            })

            # Hago resize a la imagen y paso a base64
            # base_64_img = imgToB64(pil_image)

            json_flush.append({
                "uuid": uid,
                "img": box_img_route
            })

        if len(json_data['models']) > 0:
            # salvo json
            with open(temp_config_json, 'w') as outfile:
                json.dump(json_data, outfile, indent=4)
            # pil_image.show()

            sendMsg(json_flush)
            sys.stdout.flush()
        else:
            sendMsg({
                "error": "No se encontraron rostros en la imagen seleccionada"
            })
            sys.stdout.flush()

    def save_face_models(self):
        """
        Salva los modelos seleccionados de la lista de temporales
        """
        to_save_json = json.loads(sys.argv[2])

        # Temporal config
        with open(temp_config_json, 'r') as f:
            temp_config = json.load(f)
        models = temp_config['models']

        # Current config
        with open(saved_config_json, 'r') as f:
            saved_config = json.load(f)

        # Si no encontre nada retorno
        if len(models) == 0:
            sendMsg({
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
            sendMsg({
                "message": "No se seleccionaron fotos"
            })
            cleanTempFiles()
            return

        # Copio los archivos
        for x in to_save_list:
            new_original_route = join(saved_originals_route, x['uuid']+".png")
            new_model_route = join(saved_models_route, x['uuid']+".pkl")
            new_box_route = join(saved_box_route, x['uuid']+".png")

            move(x['original_img'], new_original_route)
            move(x['img_model'], new_model_route)
            move(x['box_img'], new_box_route)

            # Agrego a la configuracion
            saved_config['models'].append({
                "original_img": new_original_route,
                "img_model": new_model_route,
                "uuid": x['uuid'],
                "box_img": new_box_route,
                "name": x['name']
            })

        # Guardo config
        with open(saved_config_json, 'w') as outfile:
            json.dump(saved_config, outfile, indent=4)

        sendMsg({
            "message": "Los rostros seleccionados fueron guardados",
            "new_models": saved_config
        })

        # Limpio la carpeta de temporales
        cleanTempFiles()

    def copy_detected_faces(self):
        """
        De una carpeta, copia todas las imagenes que tengan rostros
        entre los seleccionados,
        recibe un json con:
        - Rostros seleccionados
        - Ruta a la carpeta con grupo de imagenes
        - Ruta a la carpeta destino
        """
        config = json.loads(sys.argv[2])
        faces = config['faces']
        dest_route = config['dest']
        origin_route = config['origin']

        dest_img_list = [f for f in listdir(
            origin_route) if isImage(join(origin_route, f))]

        # Reviso que hayan imagenes
        if len(dest_img_list) == 0:
            sendMsg({
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

        for index, image in enumerate(dest_img_list):
            # Armo la ruta
            route = join(origin_route, image)
            sendMsg({
                "message": "Revisando {}".format(image),
                "state": "Running"
            })

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
                            sendMsg({
                                "message": "Encontrado rostro seleccinonado en {}".format(image),
                                "state": "Running"
                            })
                            found += 1
                            dst_route = join(dest_route, image)
                            copyfile(route, dst_route)
                            break
                            # print(faces, dest_route, origin_route)
                            # sys.stdout.flush()

        sendMsg({
            "message": "{} encontrados, finalizado con éxito.".format(found),
            "state": "Finalized"
        })

    def get_saved_configuration(self):
        with open(saved_config_json, 'r') as f:
            saved_config = json.load(f)

        sendMsg(saved_config)

    def execute_function(self, func):
        try:
            to_execute = getattr(self, func)
        except:
            print("No existe la funcion")
            return

        to_execute()


# Manejo los argumentos
handler = AppHandler()
handler.execute_function(sys.argv[1])
