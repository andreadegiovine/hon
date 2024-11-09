import logging

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN,
    SERVICE_NOTIFY,
)
from deep_translator import GoogleTranslator

from .const import APPLIANCE_DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)

class HonDevice(CoordinatorEntity):
    def __init__(self, entry, hon, coordinator, appliance, translations) -> None:
        super().__init__(coordinator)

        self._translations  = translations
        self._entry         = entry
        self._hon           = hon
        self._coordinator   = coordinator
        self._hass          = self._coordinator.hass
        self._appliance     = appliance
        self._brand         = appliance["brand"]
        self._type_name     = appliance["applianceTypeName"]
        self._type_id       = appliance["applianceTypeId"]
        self._name          = appliance.get("nickName", APPLIANCE_DEFAULT_NAME.get(str(self._type_id), "Device ID: " + str(self._type_id)))
        self._mac           = appliance["macAddress"]
        self._model         = appliance["modelName"]
        self._series        = appliance["series"]
        self._model_id      = appliance["applianceModelId"]
        self._serial_number = appliance["serialNumber"]
        self._fw_version    = appliance["fwVersion"]
        self._mac_address   = appliance["macAddress"]

        self._attributes = {}
        self._delay_time = None
        self._manually_detergent_notify = False
        self._manually_softener_notify = False
        self._low_detergent_notify = False
        self._low_softener_notify = False

    def get_stored_data(self, key):
        data = self._entry.data
        if self._mac not in data or key not in data[self._mac]:
            return {}
        return data[self._mac][key]

    def set_stored_data(self, key, value):
        data = self._entry.data.copy()
        if self._mac not in data:
            data[self._mac] = {}
        if key not in data[self._mac]:
            data[self._mac][key] = {}
        data[self._mac][key] = value
        self._hass.config_entries.async_update_entry(self._entry, data=data)
        self._hass.config_entries._async_schedule_save()
        self._coordinator.async_update_listeners()

    @property
    def settings(self):
        return self.get_stored_data("settings")

    def get_setting(self, key):
        if key not in self.settings:
            return None
        return self.settings[key]

    def update_setting(self, key, value):
        data = self.settings
        if key not in data:
            data[key] = {}
        data[key]["value"] = value
        self.set_stored_data("settings", data)

    @property
    def options(self):
        return self.get_stored_data("options")

    def get_option(self, key):
        if key not in self.options:
            return None
        return self.options[key]

    def update_option(self, key, value):
        data = self.options
        if key not in data:
            data[key] = {}
        data[key] = value
        self.set_stored_data("options", data)

    @property
    def programs(self):
        return self.get_stored_data("programs")

    def get_program(self, key):
        if key not in self.programs:
            return None
        return self.programs[key]

    def update_program(self, key, value):
        if key not in self.programs:
            return
        data = self.programs
        data[key] = value
        self.set_stored_data("programs", data)

    def get_program_params(self, key):
        data = self.get_program(key)
        if data == None:
            return None
        return data["params"]

    def update_program_params(self, name, key, value):
        data = self.get_program(name)
        if data == None or (not "params" in data) or (not key in data["params"]) or key in ["delayTime", "lang", "waterHard"]:
            return
        data["params"][key]["value"] = value
        self.update_program(name, data)

    @property
    def current_program_name(self):
        result = None
        if self.get_option("current_program"):
            result = self.get_option("current_program")
        return result

    def set_current_program(self, name):
        self.update_option("current_program", name)

    @property
    def current_program_params(self):
        if not self.current_program_name:
            return {}
        params = {**self.get_program_params(self.current_program_name)}
        for param in params:
            if param in ["delayTime", "lang", "waterHard"]:
                setting = self.get_setting(param)
                if setting != None:
                    params[param] = setting
        return params

    def get_current_program_param(self, key):
        data = self.current_program_params
        if key not in data:
            return None
        return data[key]

    def set_current_program_param(self, key, value):
        if key in ["delayTime", "lang", "waterHard"]:
            self.update_setting(key, value)
        else:
            self.update_program_params(self.current_program_name, key, value)
        self._coordinator.async_update_listeners()

    @property
    def current_program_settings(self):
        settings = {}
        params = self.current_program_params
        for param in params:
            if "value" in params[param]:
                settings[param] = str(params[param]["value"])
        return settings

    @property
    def all_params(self):
        params = {}
        for program_name in self.programs:
            params[program_name] = self.programs[program_name]["params"]
        return params

    @property
    def sensors(self):
        sensors = {"switch": [], "select": []}
        for program_name in self.all_params:
            program_options = self.all_params[program_name]
            for option_name in program_options:
                option = program_options[option_name]
                if ("type" in option) and (not option_name in sensors[option["type"]]):
                    sensors[option["type"]].append(option_name)
        for setting in self.settings:
            option = self.settings[setting]
            if "type" in option:
                sensors[option["type"]].append(setting)
        return sensors

    @property
    def is_on(self):
        return self.get_data("remoteCtrValid") == "1" and self.get_data("lastConnEvent") == "CONNECTED"

    @property
    def is_available(self):
        return self.is_on

    @property
    def is_running(self):
        if self.get_data("machMode") in ["2","3","4","5"]:
            return True
        return False

    def get_data(self, key):
        if key in self._attributes:
            return self._attributes[key]
        return None

    def set_data(self, data):
        for key in data:
            self._attributes[key] = data[key]
        self._coordinator.async_update_listeners()

    async def send_notify(self, message):
        data = {ATTR_TITLE: self._name}
        data[ATTR_MESSAGE] = message
        await self._hass.services.async_call(DOMAIN, SERVICE_NOTIFY, data)

    async def get_translation(self, string):
        translator = GoogleTranslator(source='auto', target='it')
        translated = await self._hass.async_add_executor_job(translator.translate, string)
        return translated

    def get_param_config(self, param, configs, stored_configs = None):
        result = {}
        default_value = None
        if stored_configs:
            default_value = int(stored_configs["value"])
        elif "defaultValue" in configs:
            default_value = int(configs["defaultValue"])
        if configs["typology"] == "range" and ("maximumValue" in configs):
            if int(configs["minimumValue"]) == 0 and (int(configs["maximumValue"]) == 1 or int(configs["maximumValue"]) == int(configs["incrementValue"])):
                result = {"type": "switch", "value": default_value}
            else:
                options = list(range(int(configs["minimumValue"]), (int(configs["maximumValue"])+int(configs["incrementValue"])), int(configs["incrementValue"])))
                result = {"type": "select", "value": default_value, "options": list(map(str, options))}
        elif configs["typology"] == "enum":
            result = {"type": "select", "value": default_value, "options": list(map(str, configs["enumValues"]))}
        elif "mandatory" in configs and "fixedValue" in configs:
            result = {"value": int(configs["fixedValue"])}
        if param == "delayTime":
            result["value"] = 0
        return result

    async def get_programs(self):
        commands = await self._hon.get_programs(self._appliance)
        if "startProgram" not in commands:
            return
        stored_programs = self.get_stored_data("programs")
        stored_settings = self.get_stored_data("settings")
        programs = {}
        settings = {}
        for program in commands["startProgram"]:
            program_attr = commands["startProgram"][program]
            program_name = program.split(".")[-1].lower()
            if program_name.endswith("_steam") or program_name.find("_dash_") != -1:
                continue
            program_params = {}
            for param in program_attr["parameters"]:
                configs = program_attr["parameters"][param]
                stored_configs = None
                if (param in ["delayTime", "lang", "waterHard"]):
                    if param not in settings:
                        if param in stored_settings:
                            stored_configs = stored_settings[param]
                        settings[param] = self.get_param_config(param, configs, stored_configs)
                    program_params[param] = {}
                    continue
                if (program_name in stored_programs) and ("params" in stored_programs[program_name]) and (param in stored_programs[program_name]["params"]):
                    stored_configs = stored_programs[program_name]["params"][param]
                program_params[param] = self.get_param_config(param, configs, stored_configs)
            if (program_name in stored_programs) and ("info" in stored_programs[program_name]):
                description = stored_programs[program_name]["info"]
            else:
                description = await self.get_translation(program_attr["description"])
            program_data = {"info": description, "params": program_params}
            if "remainingTimes" in program_attr:
                program_data["timing"] = program_attr["remainingTimes"]
            programs[program_name] = program_data
        self.set_stored_data("programs", programs)
        self.set_stored_data("settings", settings)
        current_program = list(programs)[0]
        if self.current_program_name:
            current_program = self.current_program_name
        self.set_current_program(current_program)

    async def get_context(self):
        data = await self._hon.get_context(self)

        attributes = {}

        for name, values in data.pop("shadow", {'NA': 0}).get("parameters").items():
            attributes[name] = values["parNewVal"]

            if name == "prPhase":
                if self._type_name.upper() == "WM":
                    if attributes[name] in ["0","10"]: # Ready
                        attributes[name] = "0"
                    if attributes[name] in ["1","2","14","15","16","25","27"]: # Wash
                        attributes[name] = "1"
                    if attributes[name] in ["3","11"]: # Spin
                        attributes[name] = "3"
                    if attributes[name] in ["4","5","6","17","18"]: # Rinse
                        attributes[name] = "4"
                    if attributes[name] in ["7","8"]: # Drying
                        attributes[name] = "7"
                    if attributes[name] in ["12","13"]: # Weighing
                        attributes[name] = "12"
                if self._type_name.upper() == "TD":
                    if attributes[name] in ["0","11"]: # Ready
                        attributes[name] = "0"
                    if attributes[name] in ["1","2","14","15","19","20"]: # Drying
                        attributes[name] = "1"
                    if attributes[name] in ["3","13","16"]: # Cooldown
                        attributes[name] = "3"
                    if attributes[name] in ["8","12","17"]: # Unknown
                        attributes[name] = "8"

        attributes["lastConnEvent"] = data["lastConnEvent"]["category"]

        if "machMode" in attributes and int(attributes["machMode"]) == 7 and self.get_data("machMode") != None and int(self.get_data("machMode")) == 2:
            await self.send_notify(self._translations.get("component.hon.entity.binary_sensor.notify.state.finished", "finished"))
            self._manually_detergent_notify = False
            self._manually_softener_notify = False

        if self._manually_softener_notify and "machMode" in attributes and int(attributes["machMode"]) == 2 and "remainingTimeMM" in attributes and int(attributes["remainingTimeMM"]) < 20:
            await self.send_pause_resume()
            await self.send_notify(self._translations.get("component.hon.entity.binary_sensor.notify.state.autosoftener_manually", "autosoftener_manually"))
            self._manually_softener_notify = False
            return

        self.set_data(attributes)

    async def send_start(self):
        if (not self.current_program_name) or (not self.current_program_settings):
            return

        params = self.current_program_settings

        if not self._low_detergent_notify and "autoDetergentStatus" in params and int(params["autoDetergentStatus"]) == 1 and self.get_data("detWarn") != None:
            if int(self.get_data("detWarn")) == 1:
                await self.send_notify(self._translations.get("component.hon.entity.binary_sensor.notify.state.autodetergent_level", "autodetergent_level"))
                self._low_detergent_notify = True
                return
            else:
                self._low_detergent_notify = False

        if not self._low_softener_notify and "autoSoftenerStatus" in params and int(params["autoSoftenerStatus"]) == 1 and self.get_data("softWarn") != None:
            if int(self.get_data("softWarn")) == 1:
                await self.send_notify(self._translations.get("component.hon.entity.binary_sensor.notify.state.autosoftener_level", "autosoftener_level"))
                self._low_softener_notify = True
                return
            else:
                self._low_softener_notify = False

        if not self._manually_detergent_notify and "autoDetergentStatus" in params and int(params["autoDetergentStatus"]) != 1:
            await self.send_notify(self._translations.get("component.hon.entity.binary_sensor.notify.state.autodetergent_manually", "autodetergent_manually"))
            self._manually_detergent_notify = True
            return

        if not self._manually_softener_notify and "autoSoftenerStatus" in params and int(params["autoSoftenerStatus"]) != 1:
            self._manually_softener_notify = True

        result = await self._hon.send_command(self, "startProgram", params, self.current_program_name)
        if result:
            new_mode = "2"
            if int(self.current_program_settings["delayTime"]) > 0:
                new_mode = "4"
            self.set_data({"machMode": new_mode})


    async def send_stop(self):
        result = await self._hon.send_command(self, "stopProgram", {"onOffStatus": "0"})
        if result:
            self.set_data({"machMode": "1"})
            self._manually_detergent_notify = False
            self._manually_softener_notify = False


    async def send_pause_resume(self):
        mode = self.get_data("machMode")

        if mode not in ["2","3"]:
            return

        pause = "1"
        command = "pauseProgram"
        new_mode = "3"
        if mode == "3":
            pause = "0"
            command = "resumeProgram"
            new_mode = "2"

        result = await self._hon.send_command(self, command, {"pause": pause})
        if result:
            self.set_data({"machMode": new_mode})
