import logging
from datetime import UTC, datetime, timedelta, timezone
import pytz

from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.helpers import translation

from .const import DOMAIN, SENSORS_DEFAULT
from .base import HonBaseDevice

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities) -> None:
    hon = hass.data[DOMAIN][entry.unique_id]
    appliances = []

    for appliance in hon.appliances:

        coordinator = await hon.async_get_coordinator(appliance)
        translations = await translation.async_get_translations(hass, hass.config.language, "entity")

        default_value = SENSORS_DEFAULT.get(coordinator.device._type_name.lower(), {})

        description = BinarySensorEntityDescription(
            key=coordinator.device._type_name.lower(),
            name=None,
            translation_key = "device",
            icon=default_value.get("icon", None),
        )
        appliances.extend([HonDevice(coordinator, appliance, description, translations)])

        await coordinator.async_request_refresh()

    async_add_entities(appliances)


class HonDevice(HonBaseDevice):
    def coordinator_update(self):
        self._attr_is_on = self._device.is_on

        attributes = {}

        if self._attr_is_on == False:
            self._attr_extra_state_attributes = attributes
            return

        if "machMode" in self._device._attributes:
            mode = self._device._attributes["machMode"]
            if mode == "5":
                mode = "4"
            attributes["mode"] = mode

        for key in ["error","errors"]:
            if key in self._device._attributes:
                if self._device._attributes[key] != "00":
                    attributes["error"] = self._device._attributes[key]

        if self._device.is_running:
            if "temp" in self._device._attributes:
                attributes["temperature"] = str(self._device._attributes["temp"]) + " °C"

            if "dryLevel" in self._device._attributes:
                dry_level = self._device._attributes["dryLevel"]
                translation_path = f"component.hon.entity.select.drylevel.state.{dry_level}"
                attributes["dry_level"] = self._translations.get(translation_path, dry_level)

            if "prCode" in self._device._attributes:
                translation_path = f"component.hon.entity.select.{self._coordinator.device._type_name.lower()}_program.state.{self._device._program}"
                attributes["program_name"] = self._translations.get(translation_path, self._device._program)

            if "prPhase" in self._device._attributes:
                pr_phase = self._device._attributes["prPhase"]
                translation_path = f"component.hon.entity.binary_sensor.{self._coordinator.device._type_name.lower()}.state_attributes.program_phase.state.{pr_phase}"
                attributes["program_phase"] = self._translations.get(translation_path, pr_phase)

            if "spinSpeed" in self._device._attributes:
                attributes["spin_speed"] = str(self._device._attributes["spinSpeed"]) + " rpm"


            if "remainingTimeMM" in self._device._attributes:
                delay = int(self._device._attributes["delayTime"])
                remaining = int(self._device._attributes["remainingTimeMM"])
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
