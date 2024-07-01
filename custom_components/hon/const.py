"""hOn component constants."""

from enum import Enum, IntEnum

DOMAIN = "hon"

CONF_ID_TOKEN = "token"
CONF_COGNITO_TOKEN = "cognito_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_FRAMEWORK = "framework"

PLATFORMS = [
    "select",
    "switch",
    "number",
    "binary_sensor",
    "button"
]

AUTH_API        = "https://account2.hon-smarthome.com/SmartHome"
API_URL         = "https://api-iot.he.services"
APP_VERSION     = "2.0.10"
OS_VERSION      = 31
OS              = "android"
DEVICE_MODEL    = "exynos9820"

class APPLIANCE_TYPE(IntEnum):
    WASHING_MACHINE = 1,
    TUMBLE_DRYER    = 8

APPLIANCE_DEFAULT_NAME = {
    "1": "Washing Machine",
    "8": "Tumble Dryer"
}