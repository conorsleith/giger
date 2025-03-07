import shelve
from threading import Lock

SETTINGS_LOCK = Lock()


class __Settings:
    def __init__(self, filename="settings"):
        self._filename = filename

    def _get_value(self, key):
        with SETTINGS_LOCK:
            with shelve.open(self._filename) as db:
                try:
                    return db[key]
                except KeyError:
                    return None

    def _set_value(self, key, value):
        with SETTINGS_LOCK:
            with shelve.open(self._filename) as db:
                db[key] = value

    @property
    def last_used_hrm_uuid(self):
        return self._get_value("hrm")

    @last_used_hrm_uuid.setter
    def last_used_hrm_uuid(self, value):
        return self._set_value("hrm", value)

    @property
    def last_used_trainer_uuid(self):
        return self._get_value("trainer")

    @last_used_trainer_uuid.setter
    def last_used_trainer_uuid(self, value):
        return self._set_value("trainer", value)


settings = __Settings()
