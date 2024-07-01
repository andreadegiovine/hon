import logging

from homeassistant.const import UnitOfTemperature, REVOLUTIONS_PER_MINUTE
from homeassistant.helpers.entity import EntityCategory
from homeassistant.components.select import SelectEntityDescription

from .const import DOMAIN
from .parameter import HonParameterFixed, HonParameterEnum, HonParameterProgram
from .base import HonBaseSelect

_LOGGER = logging.getLogger(__name__)

default_values = {
    "spinSpeed" : {
        "icon" : "mdi:speedometer",
        "unit_of_measurement" : REVOLUTIONS_PER_MINUTE,
    },
    "temp" : {
        "icon" : "mdi:thermometer",
        "unit_of_measurement" : UnitOfTemperature.CELSIUS,
    }
}

async def async_setup_entry(hass, entry , async_add_entities) -> None:
    hon = hass.data[DOMAIN][entry.unique_id]
    appliances = []

    for appliance in hon.appliances:

        coordinator = await hon.async_get_coordinator(appliance)

        for key in coordinator.device.settings:
            parameter = coordinator.device.settings[key]
            if((isinstance(parameter, HonParameterEnum) or isinstance(parameter, HonParameterProgram))
            and key.startswith("startProgram.")):

                default_value = default_values.get(parameter.key, {})

                description = SelectEntityDescription(
                    key=key,
                    name=parameter.key,
                    entity_category=EntityCategory.CONFIG,
                    translation_key=coordinator.device.appliance_type.lower() + '_' + parameter.key.lower(),
                    icon=default_value.get("icon", None),
                    unit_of_measurement=default_value.get("unit_of_measurement", None),
                )
                appliances.extend([HonSelect(coordinator, appliance, description)])

    async_add_entities(appliances)


class HonSelect(HonBaseSelect):
    @property
    def available(self) -> bool:
        return self.entity_description.key in self._device.settings and self._device.is_available() and (not self._device.is_running())

    @property
    def current_option(self) -> str | None:
        settings = self._device.settings
        value = None
        if self.entity_description.key in settings:
            value = settings[self.entity_description.key].value
        if value is None or value not in self._attr_options:
            return None
        return value

    async def async_select_option(self, option: str) -> None:
        self._device.settings[self.entity_description.key].value = option
        await self.coordinator.async_refresh()

    def coordinator_update(self):
        settings = self._device.settings
        if self.entity_description.key in settings:
            setting = settings[self.entity_description.key]
            if not isinstance(settings[self.entity_description.key], HonParameterFixed):
                self._attr_options: list[str] = setting.values
            else:
                self._attr_options: list[str] = [setting.value]
            self._attr_current_option = setting.value
        else:
            self._attr_options = []
            self._attr_current_option = None