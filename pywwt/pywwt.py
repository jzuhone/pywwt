import socket
import requests
from bs4 import BeautifulSoup
import logging
requests_log = logging.getLogger("requests")
requests_log.setLevel(logging.WARNING)
from astropy.utils.console import ProgressBar

class WWTException(Exception):
    pass

class WWTLayer(object):
    def __init__(self, name, id, fields):
        self.name = name
        self.id = id
        self.fields = fields
        
class WWTController(object):
    def __init__(self, host=None):
        if host is None:
            self.host = socket.gethostbyname(socket.gethostname())
        else:
            self.host = host
        self.wwt_url = "http://%s:5050/layerApi.aspx" % (self.host)
        if not self._check_for_server():
            raise WWTException("WWT has not been started at this address, " +
                               "or is unreachable, or is not the required version.")
        self.layers = {}
        
    def _check_for_server(self):
        try:
            params = {"cmd":"version"}
            u = requests.get(self.wwt_url, params=params)
            version_str = u.text
            soup = BeautifulSoup(version_str)
            tag = soup.layerapi.version
            version_numbers = tag.string.split(".")
            if float(".".join(version_numbers[:2])) > 2.8:
                return True
        except:
            pass
        return False

    def _handle_response(self, resp_str):
        soup = BeautifulSoup(resp_str)
        success = soup.layerapi.status.string
        if success != "Success":
            raise WWTException(success)

    def change_mode(self, mode):
        params = {}
        params["cmd"] = "mode"
        params["lookat"] = mode
        u = requests.get(self.wwt_url, params=params)
        mode_str = u.text
        self._handle_response(mode_str)

    def move_view(self, parameter):
        params = {"cmd":"move", "move":parameter}
        u = requests.get(self.wwt_url, params=params)
        move_str = u.text
        self._handle_response(move_str)

    def new_layer(self, frame, name, fields=None,
                  color=None, start_date=None,
                  end_date=None, fade_type=None,
                  fade_range=None):
        if name in self.layers:
            raise WWTException("Layer already exists with this name! Choose a different one.")
        if fields is None:
            field_string = ""
        else:
            field_string = "\t".join(fields)
        params = {}
        params["cmd"] = "new"
        params["name"] = name
        params["frame"] = frame
        params["startdate"] = start_date
        params["enddate"] = end_date
        params["fadetype"] = fade_type
        params["faderange"] = fade_range
        u = requests.post(self.wwt_url, params=params, data=field_string)
        layer_str = u.text
        soup = BeautifulSoup(layer_str)
        layer_id = soup.layerapi.findChild(name="newlayerid").string
        if len(layer_id) != 36:
            raise WWTException("Invalid Layer ID received")
        self.layers[name] = WWTLayer(name, layer_id, fields)

    def load(self, source, frame, name, color=None,
             start_date=None, end_date=None,
             fade_type=None, fade_range=None):
        from tempfile import mkstemp
        import csv
        if isinstance(source, basestring):
            filename = source
        elif isinstance(source, dict):
            handle, filename = mkstemp(suffix=".csv")
            w = csv.DictWriter(handle, source.keys())
            w.writeheader()
            num_points = len(source.values()[0])
            for i in ProgressBar(xrange(num_points)):
                row = dict([(k,v[i]) for k,v in field_dict.items()])
                w.writerow(row)
            handle.close()
        params = {}
        params["cmd"] = "load"
        params["filename"] = filename
        params["frame"] = frame
        params["color"] = color
        params["startdate"] = start_date
        params["enddate"] = end_date
        params["fadetype"] = fade_type
        params["faderange"] = fade_range
        u = requests.get(self.wwt_url, params=params)
        load_str = u.text
        self._handle_response(load_str)

    def update_layer(self, name, data,
                     no_purge=False, purge_all=False):
        layer_id = self.layers[name].id
        params = {}
        params["cmd"] = "update"
        params["id"] = layer_id
        params["purgeall"] = str(purge_all).lower()
        params["nopurge"] = str(no_purge).lower()
        fields = self.layers[name].fields
        nevents = len(data[fields[0]])
        for i in ProgressBar(xrange(nevents)):
            data_string = "\t".join([str(data[k][i]) for k in fields])
            u = requests.post(self.wwt_url, params=params, data=data_string)
            update_str = u.text
            self._handle_response(update_str)
        
    def set_properties(self, name, props_dict):
        layer_id = self.layers[name].id
        props_string = "<?xml version='1.0' encoding='UTF-8'?><LayerApi><Layer "
        for key, value in props_dict.items():
            props_string += "%s=\"%s\" " % (key, value)
        props_string += " /></LayerApi>"
        params = {}
        params["cmd"] = "setprops"
        params["id"] = layer_id
        u = requests.post(self.wwt_url, params=params, data=props_string)
        props_str = u.text
        self._handle_response(props_str)

    def activate_layer(self, name):
        layer_id = self.layers[name].id
        params = {}
        params["cmd"] = "activate"
        params["id"] = layer_id
        u = requests.get(self.wwt_url, params=params)
        layer_str = u.text
        self._handle_response(layer_str)

    def delete_layer(self, name):
        layer_id = self.layers[name].id
        params = {}
        params["cmd"] = "delete"
        params["id"] = layer_id
        u = requests.get(self.wwt_url, params=params)
        layer_str = u.text
        self._handle_response(layer_str)
        self.layers.pop(name)

    def new_layer_group(self, frame, name):
        params = {"cmd":"group",
                  "frame":frame,
                  "name":name}
        u = requests.get(self.wwt_url, params=params)
        group_str = u.text
        self._handle_response(group_str)

    def ui_settings(self, setting_name, setting_val):
        params = {"cmd":"uisettings",
                  setting_name:setting_val}
        u = requests.get(self.wwt_url, params=params)
        ui_str = u.text
        self._handle_response(ui_str)

    def get_state(self):
        params = {"cmd":"state"}
        u = requests.get(self.wwt_url, params=params)
        state_str = u.text
        self._handle_response(state_str)
        soup = BeautifulSoup(state_str)
        state = soup.layerapi.viewstate
        return state.attrs

    def get_layer_list(self, layers_only=True):
        params = {"cmd":"layerlist",
                  "layersonly":str(layers_only)}
        u = requests.get(self.wwt_url, params=params)
        layer_str = u.text
        self._handle_response(layer_str)
        soup = BeautifulSoup(layer_str)
        layer_list = soup.layerapi.layerlist
        return layer_list


    