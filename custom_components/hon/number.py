import logging

from homeassistant.const import UnitOfTime
from homeassistant.helpers.entity import EntityCategory
from homeassistant.components.number import NumberEntityDescription

from .const import DOMAIN
from .parameter import HonParameterFixed, HonParameterRange
from .base import HonBaseNumber

_LOGGER = logging.getLogger(__name__)

default_values = {
    "delayTime" : {
        "icon" : "mdi:timer-plus",
        "native_unit_of_measurement" : UnitOfTime.MINUTES
    },
    "dirtyLevel" : {
        "icon" : "mdi:liquid-spot"
    },
    "lang" : {
        "icon" : "mdi:flag"
    },
    "waterHard" : {
        "icon" : "mdi:water-percent"
    }
}

async def async_setup_entry(hass, entry, async_add_entities) -> None:
    hon = hass.data[DOMAIN][entry.unique_id]
    appliances = []

    for appliance in hon.appliances:

        coordinator = await hon.async_get_coordinator(appliance)

        for key in coordinator.device.settings:
            if key in ["startProgram.waterHard","startProgram.lang","startProgram.delayTime"]:
                continue

            parameter = coordinator.device.settings[key]
            if(isinstance(parameter, HonParameterRange)
            and key.startswith("startProgram.")
            and ( not hasattr(coordinator.device.settings[key], "min")
            or coordinator.device.settings[key].min != 0
            or not hasattr(coordinator.device.settings[key], "max")
            or coordinator.device.settings[key].max != 1)):

                default_value = default_values.get(parameter.key, {})

                description = NumberEntityDescription(
                    key=key,
                    name=parameter.key,
                    entity_category=EntityCategory.CONFIG,
                    translation_key = coordinator.device.appliance_type.lower() + '_' + parameter.key.lower(),
                    icon=default_value.get("icon", None),
                    unit_of_measurement=default_value.get("unit_of_measurement", None),
                )
                appliances.extend([HonNumber(coordinator, appliance, description)])

    async_add_entities(appliances)


class HonNumber(HonBaseNumber):
    @property
    def available(self) -> bool:
        return not isinstance(self._device.settings[self.entity_description.key], HonParameterFixed) and self._device.is_available() and (not self._device.is_running())

    @property
    def native_value(self) -> float | None:
        return self._device.get(self.entity_description.key)

    async def async_set_native_value(self, value: float) -> None:
        self._device.settings[self.entity_description.key].value = value
#         await self.coordinator.async_request_refresh()
        await self.coordinator.async_refresh()

    def coordinator_update(self):
        setting = self._device.settings[self.entity_description.key]
        if isinstance(setting, HonParameterRange):
            self._attr_native_max_value = setting.max
            self._attr_native_min_value = setting.min
            self._attr_native_step = setting.step
        self._attr_native_value = setting.value