"""
Support for collecting data from the ARWN project.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.arwn/
"""
import asyncio
import json
import logging

import homeassistant.components.mqtt as mqtt
from homeassistant.core import callback
from homeassistant.const import TEMP_FAHRENHEIT, TEMP_CELSIUS
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']
DOMAIN = 'arwn'

DATA_ARWN = 'arwn'
TOPIC = 'arwn/#'


def discover_sensors(topic, payload):
    """Given a topic, dynamically create the right sensor type.

    Async friendly.
    """
    parts = topic.split('/')
    unit = payload.get('units', '')
    domain = parts[1]
    if domain == 'temperature':
        name = parts[2]
        if unit == 'F':
            unit = TEMP_FAHRENHEIT
        else:
            unit = TEMP_CELSIUS
        return ArwnSensor(name, 'temp', unit)
    if domain == 'barometer':
        return ArwnSensor('Barometer', 'pressure', unit,
                          "mdi:thermometer-lines")
    if domain == 'wind':
        return (ArwnSensor('Wind Speed', 'speed', unit, "mdi:speedometer"),
                ArwnSensor('Wind Gust', 'gust', unit, "mdi:speedometer"),
                ArwnSensor('Wind Direction', 'direction', '°', "mdi:compass"))


def _slug(name):
    return 'sensor.arwn_{}'.format(slugify(name))


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the ARWN platform."""
    @callback
    def async_sensor_event_received(topic, payload, qos):
        """Process events as sensors.

        When a new event on our topic (arwn/#) is received we map it
        into a known kind of sensor based on topic name. If we've
        never seen this before, we keep this sensor around in a global
        cache. If we have seen it before, we update the values of the
        existing sensor. Either way, we push an ha state update at the
        end for the new event we've seen.

        This lets us dynamically incorporate sensors without any
        configuration on our side.
        """
        event = json.loads(payload)
        sensors = discover_sensors(topic, event)
        if not sensors:
            return

        store = hass.data.get(DATA_ARWN)
        if store is None:
            store = hass.data[DATA_ARWN] = {}

        if isinstance(sensors, ArwnSensor):
            sensors = (sensors, )

        if 'timestamp' in event:
            del event['timestamp']

        for sensor in sensors:
            if sensor.name not in store:
                sensor.hass = hass
                sensor.set_event(event)
                store[sensor.name] = sensor
                _LOGGER.debug("Registering new sensor %(name)s => %(event)s",
                              dict(name=sensor.name, event=event))
                async_add_devices((sensor,), True)
            else:
                store[sensor.name].set_event(event)

    yield from mqtt.async_subscribe(
        hass, TOPIC, async_sensor_event_received, 0)
    return True


class ArwnSensor(Entity):
    """Representation of an ARWN sensor."""

    def __init__(self, name, state_key, units, icon=None):
        """Initialize the sensor."""
        self.hass = None
        self.entity_id = _slug(name)
        self._name = name
        self._state_key = state_key
        self.event = {}
        self._unit_of_measurement = units
        self._icon = icon

    def set_event(self, event):
        """Update the sensor with the most recent event."""
        self.event = {}
        self.event.update(event)

    @property
    def state(self):
        """Return the state of the device."""
        return self.event.get(self._state_key, None)

    @property
    def name(self):
        """Get the name of the sensor."""
        return self._name

    @property
    def state_attributes(self):
        """Return all the state attributes."""
        return self.event

    @property
    def unit_of_measurement(self):
        """Unit this state is expressed in."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """Should we poll."""
        return False

    @property
    def icon(self):
        """Icon of device based on its type."""
        if self._icon:
            return self._icon
        else:
            return super().icon
