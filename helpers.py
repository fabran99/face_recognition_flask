from os.path import isfile, isdir, join
from os import listdir, mkdir
import re
import base64
from PIL import Image
from shutil import copyfile, rmtree
import sys
import json

from variables import reg_extension, temp_route, saved_route, json_configs
from variables import temp_config_json, saved_route_list, temp_route_list


def cleanTempFiles():
    """
    Limpia la carpeta de modelos temporales
    """
    rmtree(temp_route)
    with open(temp_config_json, 'w') as outfile:
        json.dump({
            'models': []
        }, outfile, indent=4)
    createModelsFolders()


def imgToB64(img):
    """
    Recibe una imagen de pillow, la redimensiona y 
    la retorna como base64
    """
    wpercent = (basewidth / float(img.size[0]))
    hsize = int((float(img.size[1]) * float(wpercent)))
    resized_img = img.resize((basewidth, hsize), Image.ANTIALIAS)
    return base64.b64encode(resized_img.tobytes())


def createModelsFolders():
    """
    Crea las carpetas y archivos base
    """
    # Temporal
    for x in temp_route_list:
        if not isdir(x):
            mkdir(x)

    # Guardados
    for x in saved_route_list:
        if not isdir(x):
            mkdir(x)

    # Archivos de configuracion
    for x in json_configs:
        if not isfile(x):
            with open(x, 'w') as outfile:
                json.dump({
                    'models': []
                }, outfile, indent=4)


def isImage(f):
    """
    Dada una ruta, retorna si es una imagen
    """
    return re.search(reg_extension, f) and isfile(f)


def sendMsg(msg):
    print(json.dumps(msg))
    sys.stdout.flush()
