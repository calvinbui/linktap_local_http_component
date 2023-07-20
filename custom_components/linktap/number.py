import logging

from homeassistant.components.number import NumberEntity, RestoreNumber
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity import *
from homeassistant.helpers.update_coordinator import (CoordinatorEntity,
                                                      DataUpdateCoordinator)
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)

from .const import DOMAIN, TAP_ID, GW_ID, NAME

async def async_setup_platform(
    hass, config, async_add_entities, discovery_info=None
):
    """Setup the switch platform."""
    coordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities([LinktapNumber(coordinator, hass)], True)


#class LinktapNumber(CoordinatorEntity, NumberEntity, RestoreNumber):
class LinktapNumber(CoordinatorEntity, RestoreNumber):
    def __init__(self, coordinator: DataUpdateCoordinator, hass):
        super().__init__(coordinator)
        self._state = None
        self._name = hass.data[DOMAIN]["conf"][NAME]
        self._id = self._name
        self.tap_id = hass.data[DOMAIN]["conf"][TAP_ID]
        self.platform = "number"

        self._attr_unique_id = slugify(f"{DOMAIN}_{self.platform}_{self.tap_id}")
        self._attr_device_info = self.coordinator.get_device()

        self._attr_native_min_value = 0
        self._attr_native_max_value = 120
        self._attr_native_step = 5
        self._attr_native_unit_of_measurement = "m"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        restored_number = await self.async_get_last_number_data()
        _LOGGER.debug(f"Restoring value to {restored_number.native_value}")
        self._attr_native_value = restored_number.native_value
        self.async_write_ha_state()

    @property
    def unique_id(self):
        _LOGGER.debug(self._attr_device_info)
        return self._attr_unique_id

    @property
    def name(self):
        return f"Linktap {self._name} Watering Duration"

    def set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = value
        self.async_write_ha_state()