import logging
import math
from datetime import datetime, timedelta
from typing import Any

from homeassistant.helpers.entity import EntityCategory
from homeassistant.components.switch import SwitchEntityDescription

from .const import DOMAIN, SENSORS_DEFAULT
from .base import HonBaseSwitch

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities) -> None:
    hon = hass.data[DOMAIN][entry.unique_id]
    appliances = []

    for appliance in hon.appliances:

        coordinator = await hon.async_get_coordinator(appliance)

        for key in coordinator.device.sensors["switch"]:
            default_value = SENSORS_DEFAULT.get(key, {})
            description = SwitchEntityDescription(
                key=key,
                name=key,
                entity_category=EntityCategory.CONFIG,
                translation_key=key.lower(),
                icon=default_value.get("icon", None),
            )
            appliances.extend([HonBaseSwitch(coordinator, appliance, description)])

        if "select" in coordinator.device.sensors and "delayTime" in coordinator.device.sensors["select"]:
            default_value = SENSORS_DEFAULT.get("delay", {})
            description = SwitchEntityDescription(
                key="delay",
                name="delay",
                entity_category=EntityCategory.CONFIG,
                translation_key='delayswitch',
                icon=default_value.get("icon", None),
            )
            appliances.extend([HonDelaySwitch(coordinator, appliance, description)])

    async_add_entities(appliances)


class HonDelaySwitch(HonBaseSwitch):
    @property
    def available(self) -> bool:
        return ("delayTime" in self._device._settings) and self._device.is_available and (not self._device.is_running)

    @property
    def is_on(self) -> bool | None:
        return self.available and int(self._device._settings["delayTime"]["value"]) > 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        day = datetime.now()

        if int(datetime.now().strftime("%H")) > 9:
            day = datetime.now() + timedelta(days=1)

        delay = int((day.replace(hour=9, minute=00, second=00) - datetime.now()).total_seconds() / 60)
        delay = math.floor(delay / 30) * 30

        self._device._settings["delayTime"]["value"] = str(delay)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._device._settings["delayTime"]["value"] = "0"
        await self.coordinator.async_refresh()

    def coordinator_update(self):
        if not self.available:
            self._attr_is_on = False
        else:
            self._attr_is_on = int(self._device._settings["delayTime"]["value"]) > 0