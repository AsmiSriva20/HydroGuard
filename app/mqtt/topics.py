SENSOR_SUFFIX = "/sensor"
ALERT_SUFFIX = "/alert"
STATUS_SUFFIX = "/status"


def topic_kind(topic: str) -> str | None:
    """Return 'sensor' | 'alert' | 'status' | None."""
    if topic.endswith(SENSOR_SUFFIX):
        return "sensor"
    if topic.endswith(ALERT_SUFFIX):
        return "alert"
    if topic.endswith(STATUS_SUFFIX):
        return "status"
    return None


def device_id_from_topic(topic: str) -> str | None:
    """Extract `device_id` from topics like home/{location}/{device_id}/{kind}."""
    parts = topic.split("/")
    if len(parts) < 4:
        return None
    return parts[-2]
