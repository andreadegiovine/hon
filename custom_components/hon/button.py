import logging

from homeassistant.components.button import ButtonEntityDescription

from .const import DOMAIN
from .base import HonBaseButton

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities) -> None:
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
        return self._device.is_available and self._device.get_data("machMode") in ["1","7"]

    async def async_press(self) -> None:
        await self._device.send_start()


class HonStopProgramButton(HonBaseButton):
    @property
    def available(self) -> bool:
        return self._device.is_available and self._device.get_data("machMode") in ["2","3","4","5"]

    async def async_press(self) -> None:
        await self._device.send_stop()


class HonPauseProgramButton(HonBaseButton):
    @property
    def available(self) -> bool:
        return self._device.is_available and self._device.get_data("machMode") in ["2","3"]

    async def async_press(self) -> None:
        await self._device.send_pause_resume()