import logging
import json
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.components.button import ButtonEntityDescription

from .const import DOMAIN
from .base import HonBaseButton

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities) -> None:
    hon = hass.data[DOMAIN][entry.unique_id]
    appliances = []

    for appliance in hon.appliances:

        coordinator = await hon.async_get_coordinator(appliance)

        start = ButtonEntityDescription(
            key="start",
            name="Start Program",
            icon="mdi:play",
            translation_key="start"
        )
        stop = ButtonEntityDescription(
            key="stop",
            name="Stop Program",
            icon="mdi:stop",
            translation_key="stop"
        )
        pause = ButtonEntityDescription(
            key="pause",
            name="Pause Program",
            icon="mdi:play-pause",
            translation_key="pause"
        )
        appliances.extend([HonStartProgramButton(coordinator, appliance, start, hass)])
        appliances.extend([HonStopProgramButton(coordinator, appliance, stop, hass)])
        appliances.extend([HonPauseProgramButton(coordinator, appliance, pause, hass)])

    async_add_entities(appliances)


class HonStartProgramButton(HonBaseButton):
    @property
    def available(self) -> bool:
        mode = self._device.get("machMode")
        return self._device.is_available() and mode in ["1"]

    async def async_press(self) -> None:
        """Handle the button press."""
        command = self._device.commands.get("startProgram")
        programs = command.get_programs()

        device_settings = self._device.settings

        program = device_settings["startProgram.program"].value
        if( program not in programs.keys()):
            keys = ", ".join(programs)
            raise HomeAssistantError(f"Invalid [Program] value, allowed values [{keys}]")

        command.set_program(program)
        command = self._device.commands.get("startProgram")

        parameters = json.loads(command.get_default_parameters())

        for key in parameters:
            if key in ("startProgram.waterHard","startProgram.lang"):
                continue

            if f"startProgram.{key}" in device_settings and parameters[key] != device_settings[f"startProgram.{key}"].value:
                parameters[key] = device_settings[f"startProgram.{key}"].value

        parameters["lang"] = "1"
        parameters["waterHard"] = "2"

        await self._device.start_command(program, parameters).send()
#         await self._coordinator.async_request_refresh()
        await self._device.load_context()


class HonStopProgramButton(HonBaseButton):
    @property
    def available(self) -> bool:
        mode = self._device.get("machMode")
        return self._device.is_available() and mode in ["2","3","4","5"]

    async def async_press(self) -> None:
        parameters = {"onOffStatus": "0", "machMode": "1" }
        await self._coordinator.async_set(parameters)
#         await self._coordinator.async_request_refresh()
        await self._device.load_context()


class HonPauseProgramButton(HonBaseButton):
    @property
    def available(self) -> bool:
        mode = self._device.get("machMode")
        return self._device.is_available() and mode in ["2","3"]

    async def async_press(self) -> None:
        mode = self._device.get("machMode")
        new_mode = "3"
        if mode == '3':
            new_mode = "2"
        parameters = {"onOffStatus": "1", "machMode": new_mode }
        await self._coordinator.async_set(parameters)
#         await self._coordinator.async_request_refresh()
        await self._device.load_context()