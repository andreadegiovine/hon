import logging
import aiohttp
import secrets
import json
import re
import time
from urllib import parse
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


    async def async_get_frontdoor_url(self, error_code=0):

        data = (
            "message=%7B%22actions%22%3A%5B%7B%22id%22%3A%2279%3Ba%22%2C%22descriptor%22%3A%22apex%3A%2F%2FLightningLoginCustomController%2FACTION%24login%22%2C%22callingDescriptor%22%3A%22markup%3A%2F%2Fc%3AloginForm%22%2C%22params%22%3A%7B%22username%22%3A%22"
            + parse.quote(self._email)
            + "%22%2C%22password%22%3A%22"
            + parse.quote(self._password)
            + "%22%2C%22startUrl%22%3A%22%22%7D%7D%5D%7D&aura.context=%7B%22mode%22%3A%22PROD%22%2C%22fwuid%22%3A%22"
            + parse.quote(self._framework)
            + "%22%2C%22app%22%3A%22siteforce%3AloginApp2%22%2C%22loaded%22%3A%7B%22APPLICATION%40markup%3A%2F%2Fsiteforce%3AloginApp2%22%3A%22YtNc5oyHTOvavSB9Q4rtag%22%7D%2C%22dn%22%3A%5B%5D%2C%22globals%22%3A%7B%7D%2C%22uad%22%3Afalse%7D&aura.pageURI=%2FSmartHome%2Fs%2Flogin%2F%3Flanguage%3Dfr&aura.token=null"
        )

        async with self._session.post(
            f"{AUTH_API}/s/sfsites/aura?r=3&other.LightningLoginCustom.login=1",
            headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
            data=data,
        ) as resp:
            if resp.status != 200:
                _LOGGER.error("Unable to connect to the login service: " + str(resp.status))
                return False

            text = await resp.text()
            try:
                json_data = json.loads(text)
                self._frontdoor_url = json_data["events"][0]["attributes"]["values"]["url"]
            except:
                # Framework must be updated
                if text.find("clientOutOfSync") > 0 and error_code != 2:
                    start = text.find("Expected: ") + 10
                    end = text.find(" ", start)
                    _LOGGER.debug("Framework update from ["+ self._framework+ "] to ["+ text[start:end]+ "]")
                    self._framework = text[start:end]
                    return await self.async_get_frontdoor_url(2)
                _LOGGER.error("Unable to retreive the frontdoor URL. Message: " + text)
                return 1

        if error_code == 2 and self._entry != None:
            # Update Framework
            data = {**self._entry.data}
            data[CONF_FRAMEWORK] = self._framework
            self._hass.config_entries.async_update_entry(self._entry, data=data)

        return 0

    async def async_authorize(self):

        if await self.async_get_frontdoor_url(0) == 1:
            return False

        async with self._session.get(self._frontdoor_url) as resp:
            if resp.status != 200:
                _LOGGER.error("Unable to connect to the login service: " + str(resp.status))
                return False
            await resp.text()

        url = f"{AUTH_API}/apex/ProgressiveLogin?retURL=%2FSmartHome%2Fapex%2FCustomCommunitiesLanding"
        async with self._session.get(url) as resp:
            await resp.text()
            
        url = f"{AUTH_API}/services/oauth2/authorize?response_type=token+id_token&client_id=3MVG9QDx8IX8nP5T2Ha8ofvlmjLZl5L_gvfbT9.HJvpHGKoAS_dcMN8LYpTSYeVFCraUnV.2Ag1Ki7m4znVO6&redirect_uri=hon%3A%2F%2Fmobilesdk%2Fdetect%2Foauth%2Fdone&display=touch&scope=api%20openid%20refresh_token%20web&nonce=82e9f4d1-140e-4872-9fad-15e25fbf2b7c"
        async with self._session.get(url) as resp:
            text = await resp.text()
            array = []
            try:
                array = text.split("'", 2)

                if( len(array) == 1 ):
                    #Implement a second way to get the token value
                    m = re.search('id_token\=(.+?)&', text)
                    if m:
                        self._id_token = m.group(1)
                    else:
                        _LOGGER.error("Unable to get [id_token] during authorization process (tried both options). Full response [" + text + "]")
                        return False
                else:
                    params = parse.parse_qs(array[1])
                    self._id_token = params["id_token"][0]
            except:
                _LOGGER.error("Unable to get [id_token] during authorization process. Full response [" + text + "]")
                return False

        post_headers = {"id-token": self._id_token}
        data = {
           "os": OS,
           "osVersion": OS_VERSION,
           "appVersion": APP_VERSION,
           "deviceModel": DEVICE_MODEL,
           "mobileId": self._mobile_id
       }

        async with self._session.post(f"{API_URL}/auth/v1/login", headers=post_headers, json=data) as resp:
            try:
                json_data = await resp.json()
                self._cognitoToken = json_data["cognitoUser"]["Token"]
            except:
                text = await resp.text()
                _LOGGER.error("hOn Invalid Data ["+ str(resp.text()) + "] after sending command ["+ str(data)+ "] with headers [" + str(post_headers) + "]. Response: " + text)
                return False


        url = f"{API_URL}/commands/v1/appliance"
        async with self._session.get(url,headers=self._headers) as resp:
            try:
                json_data = await resp.json()
            except:
                _LOGGER.error("hOn Invalid Data ["+ str(resp.text()) + "] after GET [" + url + "]")
                return False

            self._appliances = json_data["payload"]["appliances"]
            _LOGGER.debug(f"All appliances: {self._appliances}")

            ''' Remove appliances with no mac'''
            self._appliances = [appliance for appliance in self._appliances if "macAddress" in appliance]

            ''' Remove appliances with no applianceTypeId'''
            self._appliances = [appliance for appliance in self._appliances if "applianceTypeId" in appliance]

            ''' Remove not WM or TD appliances'''
            self._appliances = [appliance for appliance in self._appliances if appliance["applianceTypeName"] in ['WM','TD']]
    
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