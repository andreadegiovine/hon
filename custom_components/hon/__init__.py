import logging
import voluptuous as vol

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import translation

from .const import DOMAIN, PLATFORMS, CONF_MAC, CONF_DISABLED_PROGRAMS, CONF_SOFTENER_REMAINING_TIME
from .hon import HonConnection
from .device import HonDevice

_LOGGER = logging.getLogger(__name__)

HON_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAC): cv.string,
        CONF_DISABLED_PROGRAMS: vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_SOFTENER_REMAINING_TIME): int
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            vol.All(cv.ensure_list, [HON_SCHEMA])
        )
    },
    extra=vol.ALLOW_EXTRA,
)

def update_sensor(hass, device_id, mac, sensor_name, state):
    entity_reg  = er.async_get(hass)
    entries     = er.async_entries_for_device(entity_reg, device_id)

    for entry in entries:
        if( entry.unique_id == mac + '_' + sensor_name):
            inputStateObject = hass.states.get(entry.entity_id)
            hass.states.async_set(entry.entity_id, state, inputStateObject.attributes)


async def async_setup_entry(hass, entry):
    hon = HonConnection(hass, entry)
    await hon.async_authorize()

    _LOGGER.debug(f"Appliances: {hon.appliances}")

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.unique_id] = hon

    translations = await translation.async_get_translations(hass, hass.config.language, "entity")

    for appliance in hon.appliances:
        coordinator = await hon.async_get_coordinator(appliance)
        coordinator.device = HonDevice(entry, hon, coordinator, appliance, translations)
        await coordinator.async_config_entry_first_refresh()
        await coordinator.device.get_programs()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_setup(hass, config):

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["configuration_yaml"] = config.get(DOMAIN)

    return True


async def async_migrate_entry(hass, config):
    if config.version == 1 and config.minor_version < 1:
        _LOGGER.debug("Update to 1.1")
        hon = hass.data[DOMAIN][config.unique_id]
        for appliance in hon.appliances:
            coordinator = await hon.async_get_coordinator(appliance)
            coordinator.device.set_stored_data("settings", {})
            coordinator.device.set_stored_data("programs", {})

    return True
