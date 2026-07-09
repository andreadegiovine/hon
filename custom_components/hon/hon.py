import logging
import aiohttp
import secrets
import base64
import hashlib
import json
import time
from datetime import datetime
from awsiot import (mqtt5, mqtt5_client_builder)
import asyncio

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.event import async_call_later

from .base import HonBaseCoordinator
from .const import (
    CONF_ID_TOKEN,
    CONF_FRAMEWORK,
    CONF_COGNITO_TOKEN,
    CONF_REFRESH_TOKEN,
    AUTH_API,
    API_URL,
    DEVICE_MODEL,
    APP_VERSION,
    OS,
    OS_VERSION,
    AWS_ENDPOINT,
    AWS_AUTHORIZER
)

_LOGGER = logging.getLogger(__name__)

SESSION_TIMEOUT = 21600  # 6 hours session


class HonConnection:
    def __init__(self, hass, entry, email=None, password=None) -> None:
        self._hass = hass
        self._entry = entry
        self._coordinator_dict = {}
        self._mobile_id = secrets.token_hex(8)
        self._mqtt = None
        self._mqtt_connection = None

        # Only used during registration (Login/password check)
        if (email != None) and (password != None):
            self._email = email
            self._password = password
            self._framework = "None"
        else:
            self._email = entry.data[CONF_EMAIL]
            self._password = entry.data[CONF_PASSWORD]
            self._framework = entry.data.get(CONF_FRAMEWORK, "")
            self._id_token = entry.data.get(CONF_ID_TOKEN, "")
            self._refresh_token = entry.data.get(CONF_REFRESH_TOKEN, "")
            self._cognitoToken = entry.data.get(CONF_COGNITO_TOKEN, "")

        self._frontdoor_url = ""
        self._start_time = time.time()

        self._header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36"
        }
        self._session = aiohttp.ClientSession(headers=self._header)
        self._appliances = []

    @property
    def _headers(self):
        return {
            "Content-Type": "application/json",
            "cognito-token": self._cognitoToken,
            "id-token": self._id_token,
        }

    @property
    def appliances(self):
        return self._appliances

    async def async_close(self):
        await self._session.close()

    def async_get_coordinator(self, appliance):
        mac = appliance.get("macAddress", "")
        if mac in self._coordinator_dict:
            return self._coordinator_dict[mac]
        coordinator = HonBaseCoordinator(self._hass, self, appliance)
        self._coordinator_dict[mac] = coordinator
        return coordinator

    @staticmethod
    def _generate_pkce_pair():
        verifier = (
            base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode()
        )
        digest = hashlib.sha256(verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return verifier, challenge

    async def _get_session_id(self, code_challenge):
        params = {
            "username": self._email,
            "password": self._password,
            "code_challenge": code_challenge,
        }
        async with self._session.get(
                f"{API_URL}/ciam/authorize", params=params
        ) as response:
            if response.status != 200:
                _LOGGER.error("Unable to get session_id: " + str(response.status))
                _LOGGER.error(params)
                _LOGGER.error(response)
                return ""
            session_id = (await response.json()).get("session_id", "")
            if not session_id:
                _LOGGER.error("session_id missing from /ciam/authorize response")
            return session_id

    async def _get_tokens(self, session_id, code_verifier):
        async with self._session.post(
                f"{API_URL}/ciam/token",
                json={"session_id": session_id, "code_verifier": code_verifier},
        ) as response:
            if response.status != 200:
                _LOGGER.error("Unable to get tokens: " + str(response.status))
                return False
            tokens = (await response.json()).get("tokens", {})
            self._id_token = tokens.get("id_token", "")
            self._cognitoToken = tokens.get("cognito_token", "")
            self._refresh_token = tokens.get("refresh_token", "")
            if not (self._id_token and self._cognitoToken):
                _LOGGER.error("Tokens missing from /ciam/token response")
                return False
            return True

    async def async_authorize(self):
        self._session.cookie_jar.clear()

        code_verifier, code_challenge = self._generate_pkce_pair()

        session_id = await self._get_session_id(code_challenge)
        if not session_id:
            _LOGGER.error("Can't get session id")
            return False

        if not await self._get_tokens(session_id, code_verifier):
            _LOGGER.error("Can't get api tokens")
            return False

        # Carica gli appliance dal nuovo endpoint unified-api
        url = f"{API_URL}/unified-api/v1/view/appliance-list"
        payload = {"deviceId": self._mobile_id}
        async with self._session.post(url, headers=self._headers, json=payload) as resp:
            try:
                json_data = await resp.json()
            except Exception:
                _LOGGER.error("hOn Invalid Data after GET appliance-list")
                return False

            self._appliances = (
                json_data.get("modules", {})
                .get("applianceList", {})
                .get("payload", {})
                .get("appliances", [])
            )
            _LOGGER.debug(f"All appliances: {self._appliances}")

            ''' Remove appliances with no mac'''
            self._appliances = [a for a in self._appliances if "macAddress" in a]

            ''' Remove appliances with no applianceTypeId'''
            self._appliances = [a for a in self._appliances if "applianceTypeId" in a]

            ''' Remove not WM or TD appliances'''
            self._appliances = [a for a in self._appliances if a.get("applianceTypeName") in ['WM', 'TD']]

        self._start_time = time.time()
        return True

    async def get_programs(self, appliance):
        params = {
            "applianceType": appliance["applianceTypeId"],
            "code": appliance["code"],
            "applianceModelId": appliance["applianceModelId"],
            "firmwareId": appliance["eepromId"],
            "macAddress": appliance["macAddress"],
            "fwVersion": appliance["fwVersion"],
            "os": OS,
            "appVersion": APP_VERSION,
            "series": appliance["series"],
        }
        url = f"{API_URL}/commands/v1/retrieve"
        async with self._session.get(url, params=params, headers=self._headers) as resp:
            result = (await resp.json()).get("payload", {})
            if not result or result.pop("resultCode") != "0":
                return {}
            _LOGGER.debug(f"Commands: {result}")
            return result

    async def get_status(self, device):
        # Create a new hOn session to avoid reaching the expiration
        elapsed_time = time.time() - self._start_time
        if (elapsed_time > SESSION_TIMEOUT):
            await self.async_authorize()

        params = {
            "macAddress": device._mac_address,
            "applianceType": device._type_name,
            "category": "CYCLE"
        }
        url = f"{API_URL}/commands/v1/context"
        async with self._session.get(url, params=params, headers=self._headers) as response:
            data = await response.json()
            _LOGGER.debug(f"Context for mac[{device._mac_address}] type [{device._type_name}] {data}")
            return data.get("payload", {})

    async def send_command(self, device, command, parameters, program_name=False):
        now = datetime.utcnow().isoformat()
        args = {
            "macAddress": device._mac_address,
            "attributes": {
                "channel": "mobileApp",
                "origin": "standardProgram"
            },
            "device": {
                "mobileOs": OS,
                "osVersion": OS_VERSION,
                "appVersion": APP_VERSION,
                "deviceModel": DEVICE_MODEL,
                "mobileId": self._mobile_id
            },
            "ancillaryParameters": {},
            "applianceOptions": {},
            "transactionId": f"{device._mac_address}_{now[:-3]}Z",
            "commandName": command,
            "parameters": parameters
        }

        if program_name:
            args["attributes"]["energyLabel"] = "0"
            program_name = program_name.upper()
            type = device._type_name.upper()
            if type == "WM":
                type = f"{type}_WD"
            args["programName"] = f"PROGRAMS.{type}.{program_name}"

        _LOGGER.debug("Send command")
        _LOGGER.debug(args)

        async with self._session.post(f"{API_URL}/commands/v1/send", headers=self._headers, json=args, ) as resp:
            try:
                data = await resp.json()
                _LOGGER.debug((f"Command result (send_command): {data}"))
            except json.JSONDecodeError:
                _LOGGER.error("hOn Invalid Data [" + str(resp.text()) + "] after sending command [" + str(command) + "]")
                return False
            if data["payload"]["resultCode"] == "0":
                return True
            _LOGGER.error("hOn command has been rejected. Error message [" + str(data) + "] sent command [" + str(command) + "]")
        return False

    async def get_aws_token(self) -> str:
        async with self._session.get(f"{API_URL}/auth/v1/introspection", headers=self._headers) as response:
            if response.status != 200:
                _LOGGER.error("Unable to get aws token: " + str(response.status))
                return False
            token = (await response.json()).get("payload", {})
            return token.get("tokenSigned", "")

    async def start_mqtt(self):
        await self.connect_mqtt()
        self.check_mqtt_connection()

    async def connect_mqtt(self):
        try:
            self._mqtt = mqtt5_client_builder.websockets_with_custom_authorizer(
                endpoint=AWS_ENDPOINT,
                auth_authorizer_name=AWS_AUTHORIZER,
                auth_authorizer_signature=await self.get_aws_token(),
                auth_token_key_name="token",
                auth_token_value=self._id_token,
                client_id=f"pyhOn_{self._mobile_id}",
                on_lifecycle_connection_success=self._on_mqtt_connect,
                on_lifecycle_connection_failure=self._on_mqtt_disconnect,
                on_lifecycle_disconnection=self._on_mqtt_disconnect,
                on_publish_received=self._on_mqtt_message,
            )

            await self._hass.async_add_executor_job(self._mqtt.start)
            # self._mqtt.start()

            for appliance in self.appliances:
                for topic in appliance["topics"]["subscribe"]:
                    await self._hass.async_add_executor_job(
                        lambda t=topic: self._mqtt.subscribe(
                            mqtt5.SubscribePacket([mqtt5.Subscription(t)])
                        ).result(10)
                    )
                    # self._mqtt.subscribe(mqtt5.SubscribePacket([mqtt5.Subscription(topic)])).result(10)
        except Exception as e:
            _LOGGER.error("Mqtt connection error %s", str(e))
            self._mqtt_connection = False
            await self.async_authorize()
        #     return

        # async_call_later(self._hass, 5, self.check_mqtt_connection)

    def _on_mqtt_connect(self, data):
        _LOGGER.debug("_on_mqtt_connect - %s", str(data))
        self._mqtt_connection = True

    def _on_mqtt_disconnect(self, data):
        _LOGGER.debug("_on_mqtt_disconnect - %s", str(data))
        self._mqtt_connection = False

    def _on_mqtt_message(self, data):
        _LOGGER.debug("_on_mqtt_message - %s", str(data))
        if not (data and data.publish_packet and data.publish_packet.payload):
            return
        payload = json.loads(data.publish_packet.payload.decode())
        topic = data.publish_packet.topic
        _LOGGER.debug("topic - %s", topic)
        _LOGGER.debug("payload - %s", payload)

        appliance = next(
            (a for a in self.appliances if topic in a["topics"]["subscribe"]),
            None,
        )

        if appliance is None:
            _LOGGER.warning("appliance not found")
            return

        coordinator = self.async_get_coordinator(appliance)
        device = coordinator.device
        data = {}

        if topic and "appliancestatus" in topic:
            for parameter in payload["parameters"]:
                data[parameter["parName"]] = parameter
        elif topic and "disconnected" in topic:
            data = {
                "lastConnEvent": {
                    "parNewVal": "DISCONNECTED"
                }
            }
        elif topic and "connected" in topic:
            data = {
                "lastConnEvent": {
                    "parNewVal": "CONNECTED"
                }
            }

        if data:
            asyncio.run_coroutine_threadsafe(device.update_data(data), self._hass.loop).result()

    def check_mqtt_connection(self, now=None):
        _LOGGER.debug("check_mqtt_connection - %s", str(self._mqtt_connection))
        if self._mqtt_connection is False:
            _LOGGER.debug("Reconnect mqtt")
            self._mqtt_connection = None
            asyncio.run_coroutine_threadsafe(self.connect_mqtt(), self._hass.loop).result()
            # return
        async_call_later(self._hass, 20, self.check_mqtt_connection)