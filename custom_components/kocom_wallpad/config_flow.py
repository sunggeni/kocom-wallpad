"""Config flow to configure Kocom Wallpad."""

from __future__ import annotations

from typing import Any
import socket
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, LOGGER, DEFAULT_PORT


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kocom Wallpad."""

    VERSION = 1

    async def async_step_user(
        self, 
        user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((host, port))
            except socket.timeout:
                errors["base"] = "cannnot_connect"
            else:
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=host, data=user_input)
            
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
            }),
            errors=errors,
        )
    