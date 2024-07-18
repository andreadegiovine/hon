import logging

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import APPLIANCE_DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)

class HonDevice(CoordinatorEntity):
    def __init__(self, hon, coordinator, appliance) -> None:
        super().__init__(coordinator)

        self._hon           = hon
        self._coordinator   = coordinator
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
        self._programs = {}
        self._program = None
        self._settings = {}

    @property
    def sensors(self):
        sensors = {"switch": [], "select": []}
        for program_name in self._programs:
            program_options = self._programs[program_name]
            for option_name in program_options:
                option = program_options[option_name]
                if ("type" in option) and (not option_name in sensors[option["type"]]) and option_name != "lang":
                    sensors[option["type"]].append(option_name)
        return sensors

    @property
    def is_on(self):
        last_event_online = True
        if "lastConnEvent" in self._attributes:
            last_event_online = self._attributes["lastConnEvent"] != "DISCONNECTED"
        return self._attributes["remoteCtrValid"] == "1" and last_event_online

    @property
    def is_available(self):
        return self.is_on

    @property
    def is_running(self):
        if "machMode" in self._attributes:
            return self._attributes["machMode"] in ["2","3","4","5"]
        return False

    def set_program(self, program_name):
        self._program = program_name
        self._settings = self._programs[self._program]

    def set_data(self, data):
        for key in data:
            self._attributes[key] = data[key]
            self._coordinator.async_update_listeners()

    async def get_programs(self):
        commands = await self._hon.get_programs(self._appliance)

        for program in commands["startProgram"]:
            program_attr = commands["startProgram"][program]
            program_name = program.split(".")[-1].lower()

            program_params = {}
            for param in program_attr["parameters"]:
                param_attr = program_attr["parameters"][param]

                if param_attr["typology"] == "range" and ("maximumValue" in param_attr):
                    if int(param_attr["minimumValue"]) == 0 and (int(param_attr["maximumValue"]) == 1 or int(param_attr["maximumValue"]) == int(param_attr["incrementValue"])):
                        program_params[param] = {"type": "switch", "value": int(param_attr["defaultValue"])}
                    else:
                        options = list(range(int(param_attr["minimumValue"]), (int(param_attr["maximumValue"])+int(param_attr["incrementValue"])), int(param_attr["incrementValue"])))
                        program_params[param] = {"type": "select", "value": int(param_attr["defaultValue"]), "options": list(map(str, options))}
                elif param_attr["typology"] == "enum":
                    program_params[param] = {"type": "select", "value": int(param_attr["defaultValue"]), "options": list(map(str, param_attr["enumValues"]))}
                elif "mandatory" in param_attr and "fixedValue" in param_attr:
                    program_params[param] = {"value": int(param_attr["fixedValue"])}

            self._programs[program_name] = program_params

        self.set_program(list(self._programs)[0])

    async def get_context(self):
        data = await self._hon.get_context(self)

        for name, values in data.pop("shadow", {'NA': 0}).get("parameters").items():
            self._attributes[name] = values["parNewVal"]

            if name == "prPhase":
                if self._type_name.upper() == "WM":
                    if self._attributes[name] in ["0","10"]: # Ready
                        self._attributes[name] = "0"
                    if self._attributes[name] in ["1","2","14","15","16","25","27"]: # Wash
                        self._attributes[name] = "1"
                    if self._attributes[name] in ["3","11"]: # Spin
                        self._attributes[name] = "3"
                    if self._attributes[name] in ["4","5","6","17","18"]: # Rinse
                        self._attributes[name] = "4"
                    if self._attributes[name] in ["7","8"]: # Drying
                        self._attributes[name] = "7"
                    if self._attributes[name] in ["12","13"]: # Weighing
                        self._attributes[name] = "12"
                if self._type_name.upper() == "TD":
                    if self._attributes[name] in ["0","11"]: # Ready
                        self._attributes[name] = "0"
                    if self._attributes[name] in ["1","2","14","15","19","20"]: # Drying
                        self._attributes[name] = "1"
                    if self._attributes[name] in ["3","13","16"]: # Cooldown
                        self._attributes[name] = "3"
                    if self._attributes[name] in ["8","12","17"]: # Unknown
                        self._attributes[name] = "8"

        self._attributes["lastConnEvent"] = data["lastConnEvent"]["category"]

    async def send_start(self):
        if (not self._program) or (not self._settings):
            return

        params = {}

        for param in self._settings:
            attrs = self._settings[param]
            params[param] = str(attrs["value"])

        result = await self._hon.send_command(self, "startProgram", params, self._program)
        if result:
            new_mode = "2"
            if int(self._settings["delayTime"]["value"]) > 0:
                new_mode = "4"
            self.set_data({"machMode": new_mode})


    async def send_stop(self):
        result = await self._hon.send_command(self, "stopProgram", {"onOffStatus": "0"})
        if result:
            self.set_data({"machMode": "1"})


    async def send_pause_resume(self):
        mode = self._attributes["machMode"]

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



