import logging

from homeassistant.components.button import ( ButtonEntityDescription, ButtonEntity )

from .const import DOMAIN
from .base import HonBaseEntity

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
        appliances.extend([HonStartProgramButton(coordinator, appliance, start)])
        stop = ButtonEntityDescription(
            key="stop",
            name="Stop Program",
            icon="mdi:stop",
            translation_key="stop"
        )
        appliances.extend([HonStopProgramButton(coordinator, appliance, stop)])
        pause = ButtonEntityDescription(
            key="pause",
            name="Pause Program",
            icon="mdi:play-pause",
            translation_key="pause"
        )
        appliances.extend([HonPauseProgramButton(coordinator, appliance, pause)])
        reload = ButtonEntityDescription(
            key="reload",
            name="Reload Programs",
            icon="mdi:cog-refresh",
            translation_key="reload"
        )
        appliances.extend([HonReloadProgramsButton(coordinator, appliance, reload)])

    async_add_entities(appliances)


class HonStartProgramButton(HonBaseEntity, ButtonEntity):
    @property
    def available(self) -> bool:
        return self._device.is_available and self._device.get_data("machMode") in ["1","7"]

    async def async_press(self) -> None:
        await self._device.send_start()


class HonStopProgramButton(HonBaseEntity, ButtonEntity):
    @property
    def available(self) -> bool:
        return self._device.is_available and self._device.get_data("machMode") in ["2","3","4","5"]

    async def async_press(self) -> None:
        await self._device.send_stop()


class HonPauseProgramButton(HonBaseEntity, ButtonEntity):
    @property
    def available(self) -> bool:
        return self._device.is_available and self._device.get_data("machMode") in ["2","3"]

    async def async_press(self) -> None:
        await self._device.send_pause_resume()


class HonReloadProgramsButton(HonBaseEntity, ButtonEntity):
    async def async_press(self) -> None:
        await self._device.get_programs()