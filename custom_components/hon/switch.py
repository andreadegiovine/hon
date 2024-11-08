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
                entity_category=EntityCategory.DIAGNOSTIC,
                translation_key='delayswitch',
                icon=default_value.get("icon", None),
            )
            appliances.extend([HonDelaySwitch(coordinator, appliance, description)])

    async_add_entities(appliances)


class HonDelaySwitch(HonBaseSwitch):
    @property
    def available(self) -> bool:
        return self._device.get_current_program_param("delayTime") != None and "type" in self._device.get_current_program_param("delayTime") and self._device.is_available and (not self._device.is_running) and self._device._delay_time

    @property
    def is_on(self) -> bool | None:
        return self.available and int(self._device.get_current_program_param("delayTime")["value"]) > 0

    def set_delay(self):
        day = datetime.now()

        delay_hour = int(self._device._delay_time.split(":")[0])
        delay_minute = int(self._device._delay_time.split(":")[1])

        if int(datetime.now().strftime("%H")) > delay_hour-1:
            day = datetime.now() + timedelta(days=1)

        delay = int((day.replace(hour=delay_hour, minute=delay_minute, second=00) - datetime.now()).total_seconds() / 60)
        delay = math.floor(delay / 30) * 30

        if int(self._device.get_current_program_param("delayTime")["value"]) != int(delay):
            self._device.set_current_program_param("delayTime", str(delay))

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.set_delay()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._device.set_current_program_param("delayTime", "0")

    def coordinator_update(self):
        if not self.available:
            self._attr_is_on = False
        elif self._device.get_setting("delayTime"):
            self._attr_is_on = int(self._device.get_current_program_param("delayTime")["value"]) > 0
            if self._attr_is_on:
                self.set_delay()
        else:
            self._attr_is_on = False