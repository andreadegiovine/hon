import logging

from homeassistant.helpers.entity import EntityCategory
from homeassistant.components.select import SelectEntityDescription

from .const import DOMAIN, SENSORS_DEFAULT
from .base import HonBaseSelect

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry , async_add_entities) -> None:
    hon = hass.data[DOMAIN][entry.unique_id]
    appliances = []

    for appliance in hon.appliances:

        coordinator = await hon.async_get_coordinator(appliance)

        for key in coordinator.device.sensors["select"]:
            if key == "delayTime":
                default_value = SENSORS_DEFAULT.get("delay", {})
                description = SelectEntityDescription(
                    key="delay_time",
                    name="delay_time",
                    entity_category=EntityCategory.CONFIG,
                    translation_key='delayselect',
                    icon=default_value.get("icon", None),
                )
                appliances.extend([HonDelaySelect(coordinator, appliance, description)])
            else:
                default_value = SENSORS_DEFAULT.get(key, {})
                description = SelectEntityDescription(
                    key=key,
                    name=key,
                    entity_category=EntityCategory.CONFIG,
                    translation_key=key.lower(),
                    icon=default_value.get("icon", None),
                    unit_of_measurement=default_value.get("unit_of_measurement", None),
                )
                appliances.extend([HonBaseSelect(coordinator, appliance, description)])

        description = SelectEntityDescription(
            key="program",
            name="program",
            entity_category=EntityCategory.CONFIG,
            translation_key=coordinator.device._type_name.lower() + '_' + "program"
        )
        appliances.extend([HonProgramSelect(coordinator, appliance, description)])

    async_add_entities(appliances)


class HonDelaySelect(HonBaseSelect):
    @property
    def available(self) -> bool:
        return self._device.get_setting("delayTime") != None and self._device.is_available and (not self._device.is_running)

    @property
    def current_option(self) -> str | None:
        if not self.available:
            return None
        return self._device._delay_time

    async def async_select_option(self, option: str) -> None:
        self._device._delay_time = option
        await self.coordinator.async_refresh()

    def coordinator_update(self):
        if not self.available:
            self._attr_options = []
        else:
            hours = []
            for hour in list(range(0, 24, 1)):
                hour = str(hour)
                if len(hour) < 2:
                    hour = "0"+hour
                hours.append(hour+":00")
                hours.append(hour+":30")
            self._attr_options = hours


class HonProgramSelect(HonBaseSelect):
    @property
    def available(self) -> bool:
        return self._device.is_available and (not self._device.is_running)

    @property
    def current_option(self) -> str | None:
        if not self.available:
            return None
        return self._device._program

    async def async_select_option(self, option: str) -> None:
        self._device.set_program(option)
        await self.coordinator.async_refresh()

    def coordinator_update(self):
        if not self.available:
            self._attr_options = []
        else:
            self._attr_options = list(self._device._programs)
            self._attr_extra_state_attributes = self._device.get_program_details()
