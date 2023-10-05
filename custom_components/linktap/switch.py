import asyncio
import json
import logging

import aiohttp
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers.entity import *
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (CoordinatorEntity,
                                                      DataUpdateCoordinator)
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)

from .const import (ATTR_DEFAULT_TIME, ATTR_DURATION, ATTR_STATE, ATTR_VOL,
                    ATTR_VOLUME, DEFAULT_TIME, DEFAULT_VOL, DOMAIN, GW_ID,
                    GW_IP, MANUFACTURER, NAME, TAP_ID)


async def async_setup_entry(
    hass, config, async_add_entities, discovery_info=None
):
    """Setup the switch platform."""
    #taps = hass.data[DOMAIN]["conf"]["taps"]
    taps = hass.data[DOMAIN]["taps"]
    switches = []
    for tap in taps:
        coordinator = tap["coordinator"]
        coordinator_gw_id = coordinator.get_gw_id()
        _LOGGER.debug(f"Tap GWID: {tap[GW_ID]}. Coordinator GWID: {coordinator_gw_id}")
        if "switches" not in hass.data[DOMAIN]:
            hass.data[DOMAIN]["switches"] = []
        if coordinator_gw_id == tap[GW_ID] and tap not in hass.data[DOMAIN]["switches"]:
            _LOGGER.debug(f"Configuring switch for tap {tap[NAME]}")
            switches.append(LinktapSwitch(coordinator, hass, tap))
            hass.data[DOMAIN]["switches"].append(tap)
        else:
            _LOGGER.debug(f"Skipping switch for tap {tap[NAME]}")
    async_add_entities(switches, True)

class LinktapSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, coordinator: DataUpdateCoordinator, hass, tap):
        super().__init__(coordinator)
        self._state = None
        self._name = tap[NAME]
        self._id = tap[TAP_ID]
        self._gw_id = tap[GW_ID]
        self.tap_id = tap[TAP_ID]
        self.tap_api = coordinator.tap_api
        self.platform = "switch"
        self.hass = hass
        self._attr_unique_id = slugify(f"{DOMAIN}_{self.platform}_{self.tap_id}")
        self._attr_icon = "mdi:water-pump"
        self._attrs = {
            "data": self.coordinator.data,
            "duration_entity": self.duration_entity,
            "volume_entity": self.volume_entity
        }
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, tap[TAP_ID], tap[GW_ID])
            },
            name=tap[NAME],
            manufacturer=MANUFACTURER,
            model=tap[TAP_ID],
            configuration_url="http://" + tap[GW_IP] + "/"
        )

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def name(self):
        return f"{MANUFACTURER} {self._name}"

    @property
    def duration_entity(self):
        name = self._name.replace(" ", "_")
        return f"number.{DOMAIN}_{name}_watering_duration".lower()

    @property
    def volume_entity(self):
        name = self._name.replace(" ", "_")
        return f"number.{DOMAIN}_{name}_watering_volume".lower()

    async def async_turn_on(self, **kwargs):
        duration = self.get_watering_duration()
        seconds = int(float(duration)) * 60
        #volume = self.get_watering_volume()
        #watering_volume = None
        #if volume != DEFAULT_VOL:
        #    watering_volume = volume
        attributes = await self.tap_api.turn_on(self._gw_id, self.tap_id, seconds, self.get_watering_volume())
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        attributes = await self.tap_api.turn_off(self._gw_id, self.tap_id)
        await self.coordinator.async_request_refresh()

    def get_watering_duration(self):
        entity = self.hass.states.get(self.duration_entity)
        if not entity:
            _LOGGER.debug(f"Entity {self.duration_entity} not found -- setting default")
            duration = DEFAULT_TIME
            self._attrs[ATTR_DEFAULT_TIME] = True
        elif entity.state == STATE_UNKNOWN:
            _LOGGER.debug(f"Entity {self.duration_entity} state unknown -- setting default")
            duration = DEFAULT_TIME
            self._attrs[ATTR_DEFAULT_TIME] = True
        else:
            duration = entity.state
            self._attrs[ATTR_DEFAULT_TIME] = False
        self._attrs[ATTR_DURATION] = duration
        return duration

    def get_watering_volume(self):
        entity = self.hass.states.get(self.volume_entity)
        if not entity:
            volume = DEFAULT_VOL
            _LOGGER.debug(f"Entity {self.volume_entity} not found -- setting default")
            self._attrs[ATTR_VOL] = False
        elif entity.state == STATE_UNKNOWN:
            volume = DEFAULT_VOL
            _LOGGER.debug(f"Entity {self.volume_entity} state unknown -- setting default")
            self._attrs[ATTR_VOL] = False
        elif int(float(entity.state)) == 0:
            volume = entity.state
            _LOGGER.debug(f"Entity {self.volume_entity} set to 0 -- ignore")
            self._attrs[ATTR_VOL] = False
        else:
            volume = entity.state
            self._attrs[ATTR_VOL] = True
        self._attrs[ATTR_VOLUME] = volume
        return volume

    @property
    def extra_state_attributes(self):
        return self._attrs

    @property
    def state(self):
        status = self.coordinator.data
        self._attrs["data"] = status
        _LOGGER.debug(f"Switch Status: {status}")
        duration = self.get_watering_duration()
        _LOGGER.debug(f"Set duration:{duration}")
        volume = self.get_watering_volume()
        _LOGGER.debug(f"Set volume:{volume}")
        self._attrs[ATTR_STATE] = status[ATTR_STATE]
        state = "unknown"
        if status[ATTR_STATE]:
            state = "on"
        elif not status[ATTR_STATE]:
            state = "off"
            _LOGGER.debug(f"Switch {self.name} state {state}")
        return state

    @property
    def is_on(self):
        return self.state()

    @property
    def device_info(self) -> DeviceInfo:
        return self._attr_device_info
