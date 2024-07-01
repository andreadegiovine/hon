import logging
from datetime import UTC, datetime, timedelta, timezone
import pytz
import asyncio

from homeassistant.components.binary_sensor import ( BinarySensorEntity, BinarySensorEntityDescription )
from homeassistant.helpers import translation

from .const import DOMAIN, APPLIANCE_TYPE
from .base import HonBaseDevice

_LOGGER = logging.getLogger(__name__)

default_values = {
    "wm" : {
        "icon" : "mdi:washing-machine",
    },
    "td" : {
        "icon" : "mdi:tumble-dryer",
    },
}

async def async_setup_entry(hass, entry, async_add_entities) -> None:
    hon = hass.data[DOMAIN][entry.unique_id]
    appliances = []

    for appliance in hon.appliances:

        coordinator = await hon.async_get_coordinator(appliance)
        translations = await translation.async_get_translations(hass, hass.config.language, "entity")

        default_value = default_values.get(coordinator.device.appliance_type.lower(), {})

        description = BinarySensorEntityDescription(
            key=coordinator.device.appliance_type.lower(),
            name=None,
            translation_key = coordinator.device.appliance_type.lower(),
            icon=default_value.get("icon", None),
        )
        appliances.extend([HonDevice(coordinator, appliance, description, translations)])

        await coordinator.async_request_refresh()

    async_add_entities(appliances)


class HonDevice(HonBaseDevice):
    def coordinator_update(self):
        self._attr_is_on = self._device.is_on()

        if self._attr_is_on == False:
            return

        attributes = {}

        if self._device.has("machMode"):
            attributes["mode"] = self._device.get("machMode")

        if self._device.has("onOffStatus"):
            attributes["status"] = self._device.get("onOffStatus")

        for key in ["error","errors"]:
            if self._device.has(key):
                if self._device.get(key) != "00":
                    attributes["error"] = self._device.get(key)

        if self._device.has("temp"):
            if self._device.is_running():
                attributes["temperature"] = str(self._device.get("temp")) + " °C"

        if self._device.has("dryLevel"):
            if self._device.is_running():
                attributes["dry_level"] = self._device.get("dryLevel")

        if self._device.has("prCode"):
            if self._device.is_running():
                translation_path = f"component.hon.entity.select.{self._coordinator.device.appliance_type.lower()}_program.state.{self._device.getProgramName()}"
                attributes["program_name"] = self._translations.get(translation_path, self._device.getProgramName())

        if self._device.has("prPhase"):
            if self._device.is_running():
                attributes["program_phase"] = self._device.get("prPhase")

        if self._device.has("spinSpeed"):
            if self._device.is_running():
                attributes["spin_speed"] = str(self._device.get("spinSpeed")) + " rpm"

        if self._device.has("remainingTimeMM"):
            if self._device.is_running():
                delay = self._device.getInt("delayTime")
                remaining = self._device.getInt("remainingTimeMM")
                value = None
                if remaining > 0:
                    value = datetime.now(timezone.utc).replace(second=0) + timedelta(minutes=delay + remaining)

                    if remaining//60 > 0:
                        remaining = str(remaining//60) + ":" + str(remaining%60)
                    else:
                        remaining = str(remaining) + " min"
                else:
                    remaining: None

                attributes["remaining_time"] = remaining

                if (not value in [0, None]) and value.tzinfo != UTC:
                    value = value.astimezone(UTC)

                value = value.astimezone(pytz.timezone('Europe/Rome'))
                attributes["end_time"] = value.strftime("%H:%M")

        self._attr_extra_state_attributes = attributes
