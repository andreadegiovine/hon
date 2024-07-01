import logging
import re
from typing import Any
from datetime import timedelta
import time

from homeassistant.helpers.update_coordinator import ( DataUpdateCoordinator, CoordinatorEntity, REQUEST_REFRESH_DEFAULT_COOLDOWN )
from homeassistant.core import callback
from homeassistant.components.select import SelectEntity
from homeassistant.components.button import ButtonEntity
from homeassistant.components.number import NumberEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import DOMAIN, APPLIANCE_DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)

class HonBaseCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, hon, appliance):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="hOn Device",
            update_interval=timedelta(seconds=30),
        )
        self._hon       = hon
        self._device    = None
        self._appliance = appliance

        try:
            self._mac           = appliance["macAddress"]
            self._type_name     = appliance["applianceTypeName"]
            self._type_id       = appliance["applianceTypeId"]
            self._name          = appliance.get("nickName", APPLIANCE_DEFAULT_NAME.get(str(self._type_id), "Device ID: " + str(self._type_id)))
            self._brand         = appliance["brand"]
            self._model         = appliance["modelName"]
            self._fw_version    = appliance["fwVersion"]
        except:
            _LOGGER.warning(f"Invalid appliance data in {appliance}" )


    async def _async_update_data(self):
        await self._device.load_context()

    @property
    def device(self):
        return self._device

    @device.setter
    def device(self, value):
        self._device = value

    async def async_set(self, parameters):
        await self._hon.async_set(self._mac, self._type_name, parameters)

    def get(self, key):
        return self.data.get(key, "")

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self._mac, self._type_name)
            },
            "name": self._name,
            "manufacturer": self._brand,
            "model": self._model,
            "sw_version": self._fw_version,
        }

class HonBaseEntity(CoordinatorEntity):
    def __init__(self, coordinator, appliance, description):
        super().__init__(coordinator)

        """Hon properties"""
        self._coordinator           = coordinator
        self._mac                   = appliance["macAddress"]
        self._type_id               = appliance["applianceTypeId"]
        self._name                  = appliance.get("nickName", APPLIANCE_DEFAULT_NAME.get(str(self._type_id), "Device ID: " + str(self._type_id)))
        self._brand                 = appliance["brand"]
        self._model                 = appliance["modelName"]
        self._fw_version            = appliance["fwVersion"]
        self._type_name             = appliance["applianceTypeName"]
        self._sensor_name           = description.name
        self._key                   = description.key
        self._device                = coordinator.device
        self._translations          = None

        """Homeassistant properties"""
        key_formatted = re.sub(r'(?<!^)(?=[A-Z])', '_', self._key).lower()
        if( len(key_formatted) <= 0 ):
            key_formatted = re.sub(r'(?<!^)(?=[A-Z])', '_', self._sensor_name).lower()

        self.entity_description     = description
        self._attr_translation_key  = description.translation_key
        self._attr_has_entity_name  = True
        self._attr_unique_id        = self._mac + "_" + key_formatted

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self._mac, self._type_name)
            },
            "name": self._name,
            "manufacturer": self._brand,
            "model": self._model,
            "sw_version": self._fw_version,
        }

    @property
    def available(self) -> bool:
        """Entity is available"""
        return True



"""Used for update device settings"""
class HonBaseSensor(HonBaseEntity):
    def __init__(self, coordinator, appliance, description):
        super().__init__(coordinator, appliance, description)

        """First update"""
        self.coordinator_update()

    @callback
    def _handle_coordinator_update(self):
        if self._coordinator.data is False:
            return
        self.coordinator_update()
        self.async_write_ha_state()

    def coordinator_update(self):
        """Update entity state"""
        raise NotImplementedError



class HonBaseButton(HonBaseEntity, ButtonEntity):
    def __init__(self, coordinator, appliance, description, hass):
        super().__init__(coordinator, appliance, description)
        self._hass                   = hass
#         self.auto_detergent_notified = False
#         self.auto_softener_notified  = False

    async def async_press(self):
        """Press on button action"""
        raise NotImplementedError

class HonBaseSelect(HonBaseSensor, SelectEntity):
    @property
    def current_option(self):
        """Press on button action"""
        raise NotImplementedError

    async def async_select_option(self, option: str):
        """Press on button action"""
        raise NotImplementedError

class HonBaseNumber(HonBaseSensor, NumberEntity):
    @property
    def native_value(self):
        """Press on button action"""
        raise NotImplementedError

    async def async_set_native_value(self, value: float):
        """Press on button action"""
        raise NotImplementedError

class HonBaseSwitch(HonBaseSensor, SwitchEntity):
    @property
    def is_on(self):
        """Press on button action"""
        raise NotImplementedError

    async def async_turn_on(self, **kwargs: Any):
        """Press on button action"""
        raise NotImplementedError

    async def async_turn_off(self, **kwargs: Any):
        """Press on button action"""
        raise NotImplementedError

    def coordinator_update(self):
        self._attr_is_on = self.is_on


class HonBaseDevice(HonBaseEntity, BinarySensorEntity):
    def __init__(self, coordinator, appliance, description, translations):
        super().__init__(coordinator, appliance, description)
        self._translations           = translations

        """First update"""
        self.coordinator_update()

    @callback
    def _handle_coordinator_update(self):
        if self._coordinator.data is False:
            return
        self.coordinator_update()
        self.async_write_ha_state()

    def coordinator_update(self):
        """Update entity state"""
        raise NotImplementedError
