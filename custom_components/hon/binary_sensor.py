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

    translations = await translation.async_get_translations(hass, hass.config.language, "entity")

    for appliance in hon.appliances:

        coordinator = await hon.async_get_coordinator(appliance)

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
    def get_program_duration(self):
        program_data = self._device.get_program(self._device.current_program_name)
        if "timing" not in program_data:
            return None
        timing = 0
        timing_data = program_data["timing"]
        for option in timing_data:
            if self._device.get_current_program_param(option) and "value" in self._device.get_current_program_param(option):
                option_setting = self._device.get_current_program_param(option)["value"]
                option_setting = str(option_setting)
                if option in ["dirtyLevel","dryLevel","dryTime"]:
                    timing = timing + int(timing_data[option][option_setting])
                elif option == "steamLevel":
                    timing = timing + int(timing_data["steamLevel"]["+steamType"][option_setting])
                else:
                    for phase in timing_data[option]:
                        timing = timing + int(timing_data[option][phase][option_setting])
        if timing//60 > 0:
            timing = str(timing//60) + ":" + str(timing%60)
        else:
            timing = str(timing) + " min"
        return timing

    def coordinator_update(self):
        self._attr_is_on = self._device.is_on

        attributes = {}

        if self._attr_is_on == False:
            self._attr_extra_state_attributes = attributes
            return

        if self._device.get_data("machMode"):
            mode = self._device.get_data("machMode")
            if mode == "5":
                mode = "4"
            attributes["mode"] = mode

        for key in ["error","errors"]:
            if self._device.get_data(key) and self._device.get_data(key) != "00":
                attributes["error"] = self._device.get_data(key)

        if self._device.is_running:
            if self._device.get_data("temp"):
                attributes["temperature"] = str(self._device.get_data("temp")) + " °C"

            if self._device.get_data("dryLevel"):
                dry_level = self._device.get_data("dryLevel")
                translation_path = f"component.hon.entity.select.drylevel.state.{dry_level}"
                attributes["dry_level"] = self._translations.get(translation_path, dry_level)

            if self._device.get_data("prPhase"):
                pr_phase = self._device.get_data("prPhase")
                translation_path = f"component.hon.entity.binary_sensor.{self._coordinator.device._type_name.lower()}.state_attributes.program_phase.state.{pr_phase}"
                attributes["program_phase"] = self._translations.get(translation_path, pr_phase)

            if self._device.get_data("spinSpeed"):
                attributes["spin_speed"] = str(self._device.get_data("spinSpeed")) + " rpm"


            if self._device.get_data("remainingTimeMM"):
                delay = int(self._device.get_data("delayTime"))
                remaining = int(self._device.get_data("remainingTimeMM"))
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

        if self._device.current_program_name:
            translation_path = f"component.hon.entity.select.{self._coordinator.device._type_name.lower()}_program.state.{self._device.current_program_name}"
            attributes["program_name"] = self._translations.get(translation_path, self._device.current_program_name)

            attributes["program_description"] = self._device.get_program(self._device.current_program_name)["info"]
            attributes["program_duration"] = self.get_program_duration()

            params = self._device.current_program_settings
            for param in params:
                attributes["program_"+param] = params[param]

        self._attr_extra_state_attributes = attributes
