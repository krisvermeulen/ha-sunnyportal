"""Support for SunnyPortal Sensors."""
from datetime import date
from datetime import timedelta
import logging

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MONITORED_VARIABLES,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import voluptuous as vol


from sunnyportal.client import Client as SunnyPortalClient


_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)

# Sensor types are defined like so: Name, unit, icon
SENSOR_TYPES = {
    "day_generated_energy": [
        "Sunny Portal Energy Generated Today",
        "mdi:white-balance-sunny",
    ],
    "overall_generated_energy": [
        "Sunny Portal Total Energy Generated",
        "mdi:white-balance-sunny",
    ],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_MONITORED_VARIABLES): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the QNAP NAS sensor."""
    api = SunnyPortalAPI(config)
    api.update()

    # SunnyPortal is not available
    if not api.data:
        raise PlatformNotReady


    sensors = []
    for plant_name in api.data:
        _LOGGER.info("Discovered plant %s", plant_name)
        for sensor_type in config[CONF_MONITORED_VARIABLES]:
            sensors.append(SunnyPortalSensor(api, plant_name, sensor_type))

    add_entities(sensors)


class SunnyPortalAPI:
    """Class to interface with the API."""

    def __init__(self, config):
        """Initialize the API wrapper."""

        self._sunnyPortalClient = SunnyPortalClient(config.get(CONF_USERNAME), config.get(CONF_PASSWORD))
        self.data = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update API information and store locally."""
        try:
            for plant in self._sunnyPortalClient.get_plants():
                last_data = plant.last_data_exact(date.today())
                self.data[plant.name] = {
                    "day_energy": round(last_data.day.difference / 1000, 3),
                    "absolute_energy": round(last_data.day.absolute / 1000, 3),
                    "unit_of_measurement": "kWh"
                }

            self._sunnyPortalClient.logout()
        except:  # noqa: E722 pylint: disable=bare-except
            _LOGGER.exception("Failed to fetch stats from sunny portal")


class SunnyPortalSensor(Entity):
    """Base class for a Sunny Portal sensor."""

    def __init__(self, api, plant_name, sensor_type):
        """Initialize the sensor."""
        self.plant_name = plant_name
        self.type = sensor_type
        self.entity_id = f"sunnyportal.{self.plant_name}_{sensor_type}".lower()
        self._name = SENSOR_TYPES[sensor_type][0]
        self._icon = SENSOR_TYPES[sensor_type][1]
        self._unit_of_measurement = None
        self._state = None
        self._api = api

    @property
    def name(self):
        """Return the name of the sensor, if any."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

#    @property
#    def device_state_attributes(self):
#        """Return the state attributes."""
#        if self._api.data:
#            data = self._api.data["system_stats"]["memory"]
#            size = round_nicely(float(data["total"]) / 1024)
#            return {ATTR_MEMORY_SIZE: f"{size} {DATA_GIBIBYTES}"}

    def update(self):
        """Get the latest data for the states."""
        self._api.update()
        if self.type == "day_generated_energy":
            self._state = self._api.data[self.plant_name]["day_energy"]
            self._unit_of_measurement = self._api.data[self.plant_name]["unit_of_measurement"]
        elif self.type == "ovetall_generated_energy":
            self._state = self._api.data[self.plant_name]["absolute_energy"]
            self._unit_of_measurement = self._api.data[self.plant_name]["unit_of_measurement"]


