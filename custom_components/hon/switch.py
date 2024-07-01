import logging
import datetime
import math
from typing import Any

from homeassistant.helpers.entity import EntityCategory
from homeassistant.components.switch import SwitchEntityDescription

from .const import DOMAIN
from .parameter import HonParameter, HonParameterFixed, HonParameterRange
from .base import HonBaseSwitch

_LOGGER = logging.getLogger(__name__)

default_values = {
    "acquaplus" : {
        "icon" : "mdi:water-plus",
    },
    "anticrease" : {
        "icon" : "mdi:mirror-rectangle",
    },
    "autoDetergentStatus" : {
        "icon" : "mdi:water-check",
    },
    "autoSoftenerStatus" : {
        "icon" : "mdi:flower-poppy",
    },
    "extraRinse1" : {
        "icon" : "mdi:water-sync",
    },
    "extraRinse2" : {
        "icon" : "mdi:water-sync",
    },
    "extraRinse3" : {
        "icon" : "mdi:water-sync",
    },
    "goodNight" : {
        "icon" : "mdi:weather-night",
    },
    "hygiene" : {
        "icon" : "mdi:virus-off",
    },
    "prewash" : {
        "icon" : "mdi:sync",
    },
    "delay" : {
        "icon" : "mdi:timer-plus",
    }
}

async def async_setup_entry(hass, entry, async_add_entities) -> None:
    hon = hass.data[DOMAIN][entry.unique_id]
    appliances = []

    for appliance in hon.appliances:

        coordinator = await hon.async_get_coordinator(appliance)

        for key in coordinator.device.settings:
            parameter = coordinator.device.settings[key]
            if(isinstance(parameter, HonParameterRange)
            and key.startswith("startProgram.")
            and hasattr(coordinator.device.settings[key], "min")
            and coordinator.device.settings[key].min == 0
            and hasattr(coordinator.device.settings[key], "max")
            and coordinator.device.settings[key].max == 1):

                default_value = default_values.get(parameter.key, {})

                description = SwitchEntityDescription(
                    key=key,
                    name=parameter.key,
                    entity_category=EntityCategory.CONFIG,
                    translation_key = coordinator.device.appliance_type.lower() + '_' + parameter.key.lower(),
                    icon=default_value.get("icon", None),
                )
                appliances.extend([HonSwitch(coordinator, appliance, description)])

    default_value = default_values.get("delay", {})

    description = SwitchEntityDescription(
        key="delay",
        name="delay",
        entity_category=EntityCategory.CONFIG,
        translation_key = coordinator.device.appliance_type.lower() + '_delay',
        icon=default_value.get("icon", None),
    )
    appliances.extend([HonDelaySwitch(coordinator, appliance, description)])

    async_add_entities(appliances)


class HonSwitch(HonBaseSwitch):
    @property
    def available(self) -> bool:
        return not isinstance(self._device.settings[self.entity_description.key], HonParameterFixed) and self._device.is_available() and (not self._device.is_running())

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        setting = self._device.settings[self.entity_description.key]
        return int(setting.value) == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        setting = self._device.settings[self.entity_description.key]
        if type(setting) == HonParameter:
            return
        setting.value = "1"
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        setting = self._device.settings[self.entity_description.key]
        if type(setting) == HonParameter:
            return
        setting.value = "0"
        await self.coordinator.async_request_refresh()


class HonDelaySwitch(HonBaseSwitch):
    @property
    def available(self) -> bool:
        return self._device.is_available() and (not self._device.is_running())

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        setting = self._device.settings["startProgram.delayTime"]
        return int(setting.value) > 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        day = datetime.datetime.now()
        if int(datetime.datetime.now().strftime("%H")) > 9:
            day = datetime.datetime.now() + datetime.timedelta(days=1)
        delay = int((day.replace(hour=9, minute=00, second=00) - datetime.datetime.now()).total_seconds() / 60)
        delay = math.floor(delay / 30) * 30

        setting = self._device.settings["startProgram.delayTime"]
        setting.value = str(delay)

#         await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        setting = self._device.settings["startProgram.delayTime"]
        setting.value = "0"

#         await self.coordinator.async_request_refresh()