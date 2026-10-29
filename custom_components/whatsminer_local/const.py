"""Integration constants."""
DOMAIN = "whatsminer_local"
DEFAULT_PORT = 4433
DEFAULT_INTERVAL = 30
CONF_CONTROL = "enable_control"
CONF_MIN = "min_power"
CONF_MAX = "max_power"
CONF_ACCOUNT = "account"
ACCOUNTS = ("super", "user1", "user2", "user3")

CONF_PERCENT_MIN = "min_power_percent"
CONF_PERCENT_MODE = "power_percent_mode"
CONF_WEB_CHIPS = "web_chips"
CONF_WEB_SCAN_INTERVAL = "web_scan_interval"
CONF_WEB_PROTOCOL = "web_protocol"
CONF_WEB_PORT = "web_port"
CONF_WEB_PATH = "web_path"
CONF_WEB_POINTER = "web_json_pointer"
CONF_WEB_AUTH = "web_auth"
CONF_WEB_USERNAME = "web_username"
CONF_WEB_PASSWORD = "web_password"
CONF_WEB_COOKIE = "web_cookie"
CONF_WEB_VERIFY_SSL = "web_verify_ssl"
DEFAULT_WEB_PATH = "/cgi-bin/luci/admin/status/btminerapi"
DEFAULT_WEB_PROTOCOL = "https"
DEFAULT_WEB_PORT = 443
DEFAULT_WEB_INTERVAL = 3600
LEGACY_WEB_OPTIONS = frozenset({
    CONF_WEB_PROTOCOL, CONF_WEB_PORT, CONF_WEB_PATH, CONF_WEB_POINTER,
    CONF_WEB_AUTH, CONF_WEB_COOKIE,
})
DEFAULT_PERCENT_MIN = 50
CARD_URL = "/ha-whatsminer/ha-whatsminer-heatmap-card.js"
