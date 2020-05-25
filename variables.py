from os.path import join
# expresion regular para filtrar las imagenes
reg_extension = "\.jpg|\.png|\.jpeg|\.gif|\.JPG|\.PNG|\.JPEG|\.GIF$"

# Routes temp
temp_route = '.\\temp_models'
temp_originals_route = join(temp_route, "originals")
temp_models_route = join(temp_route, "models")
temp_box_route = join(temp_route, "box")

temp_route_list = [temp_route,
                   temp_originals_route,
                   temp_models_route,
                   temp_box_route]


# Routes saved
saved_route = '.\\saved_models'
saved_originals_route = join(saved_route, "originals")
saved_models_route = join(saved_route, "models")
saved_box_route = join(saved_route, "box")

saved_route_list = [saved_route,
                    saved_originals_route,
                    saved_models_route,
                    saved_box_route]

# Json configs
temp_config_json = '.\\temp_config.json'
saved_config_json = '.\\saved_config.json'

json_configs = [temp_config_json, saved_config_json]

# Ancho img
basewidth = 500

face_distance_tolerance = 0.6
