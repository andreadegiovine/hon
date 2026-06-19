import logging
import aiohttp
import secrets
import base64
import hashlib
import json
import time
from datetime import datetime

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

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
    OS_VERSION
)

_LOGGER = logging.getLogger(__name__)

SESSION_TIMEOUT = 21600 # 6 hours session

class HonConnection:
    def __init__(self, hass, entry, email = None, password = None) -> None:
        self._hass = hass
        self._entry = entry
        self._coordinator_dict  = {}
        self._mobile_id = secrets.token_hex(8)

        # Only used during registration (Login/password check)
        if( email != None ) and ( password != None ):
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
        self._start_time    = time.time()

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
        
    async def async_get_coordinator(self, appliance):
        mac = appliance.get("macAddress", "")
        if mac in self._coordinator_dict:
            return self._coordinator_dict[mac]
        coordinator = HonBaseCoordinator( self._hass, self, appliance)
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

    async def get_context(self, device):
        # Create a new hOn session to avoid reaching the expiration
        elapsed_time = time.time() - self._start_time
        if( elapsed_time > SESSION_TIMEOUT ):
            self._session.cookie_jar.clear()
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


    async def send_command(self, device, command, parameters, program_name = False):
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

        async with self._session.post(f"{API_URL}/commands/v1/send",headers=self._headers,json=args,) as resp:
            try:
                data = await resp.json()
                _LOGGER.debug((f"Command result (send_command): {data}"))
            except json.JSONDecodeError:
                _LOGGER.error("hOn Invalid Data ["+ str(resp.text()) + "] after sending command ["+ str(command)+ "]")
                return False
            if data["payload"]["resultCode"] == "0":
                return True
            _LOGGER.error("hOn command has been rejected. Error message ["+ str(data) + "] sent command ["+ str(command)+ "]")
        return False