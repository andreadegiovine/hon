"""hOn component constants."""

from enum import Enum, IntEnum
from homeassistant.const import UnitOfTemperature, REVOLUTIONS_PER_MINUTE

DOMAIN = "hon"

CONF_ID_TOKEN = "token"
CONF_COGNITO_TOKEN = "cognito_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_FRAMEWORK = "framework"
CONF_MAC = "mac"
CONF_DISABLED_PROGRAMS = "disabled_programs"
CONF_SOFTENER_REMAINING_TIME = "softener_remaining_time"

PLATFORMS = [
    "select",
    "switch",
    "binary_sensor",
    "button"
]

SENSORS_DEFAULT = {
    "wm" : {
        "icon" : "mdi:washing-machine",
    },
    "td" : {
        "icon" : "mdi:tumble-dryer",
        "binary_sensors": {
            "dryFilterStatus": {
                "icon": "mdi:air-filter",
            }
        }
    },
    "acquaplus" : {
        "icon" : "mdi:water-plus",
    },
    "anticrease" : {
        "icon" : "mdi:mirror-rectangle",
    },
    "autoDetergentStatus" : {
        "icon" : "mdi:water-check",
    },
    "autoSoftenerStatus" : {
        "icon" : "mdi:flower-poppy",
    },
    "extraRinse1" : {
        "icon" : "mdi:water-sync",
    },
    "extraRinse2" : {
        "icon" : "mdi:water-sync",
    },
    "extraRinse3" : {
        "icon" : "mdi:water-sync",
    },
    "goodNight" : {
        "icon" : "mdi:weather-night",
    },
    "hygiene" : {
        "icon" : "mdi:virus-off",
    },
    "prewash" : {
        "icon" : "mdi:sync",
    },
    "delay" : {
        "icon" : "mdi:timer-plus",
    },
    "dryLevel" : {
        "icon" : "mdi:water-opacity",
    },
    "dryTime" : {
        "icon" : "mdi:fan-clock",
    },
    "dirtyLevel" : {
        "icon" : "mdi:liquid-spot",
    },
    "lang" : {
        "icon" : "mdi:translate",
    },
    "steamLevel" : {
        "icon" : "mdi:weather-dust",
    },
    "waterHard" : {
        "icon" : "mdi:water-percent",
    },
    "bestIroning" : {
        "icon" : "mdi:iron",
    },
    "spinSpeed" : {
        "icon" : "mdi:speedometer",
        "unit_of_measurement" : REVOLUTIONS_PER_MINUTE,
    },
    "temp" : {
        "icon" : "mdi:thermometer",
        "unit_of_measurement" : UnitOfTemperature.CELSIUS,
    }
}

AUTH_API        = "https://account2.hon-smarthome.com/SmartHome"
API_URL         = "https://api-iot.he.services"
APP_VERSION     = "2.10.6"
OS_VERSION      = "15.7.1"
OS              = "ios"
DEVICE_MODEL    = "iphonexs"

class APPLIANCE_TYPE(IntEnum):
    WASHING_MACHINE = 1,
    TUMBLE_DRYER    = 8

APPLIANCE_DEFAULT_NAME = {
    "1": "Washing Machine",
    "8": "Tumble Dryer"
}