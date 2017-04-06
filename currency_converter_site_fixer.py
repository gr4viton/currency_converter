
import arrow
from currency_converter_site import CurrencyConverterSite
from parameter_names_enums import JsonParameterNames as jpn
import requests
import time

import logging
#logging.basicConfig(filename='run.log', filemode='w', level=logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)

from logging import info as prinf
from logging import debug as prind
from logging import warning as prinw

class CurrencyConverterSiteFixer(CurrencyConverterSite):
    name = 'fixer'

    def __init__(self, name, base, strs):
        self.name = name
        self.base = base
        self.strs = strs
        self.my_params = None
        self.rates = None

        self.valid_from_utc = None
        self.valid_to_utc = None

    def create_url(self):
        self.base_url = self.base + self.strs[jpn.path_latest]

    def update_params(self, in_ccode, out_ccode=None):
        self.my_params.update({self.strs[jpn.var_in_ccode] : in_ccode})
        if out_ccode:
            self.my_params.update({self.strs[jpn.var_out_ccode] : out_ccode})

    def stamp_datetime(self):
        date_cet = self.response.json()[self.strs[jpn.key_date]]
        fmt = self.strs[jpn.key_date_format]
        date_time = arrow.get(date_cet, fmt)
        self.valid_from_utc = self.__class__.stamp_time(date_time)
        prinf('%s valid_from_utc', self.valid_from_utc)
        self.valid_to_utc = self.__class__.stamp_valid_to(self.valid_from_utc)
        prinf('%s valid_to_utc', self.valid_to_utc)
        prinf('%s now', arrow.utcnow())

    @staticmethod
    def stamp_time(utc):
        # fixer.io = The rates are updated daily around 4PM CET.
        # Central European Time is 1 hour ahead of Coordinated Universal Time
        # = 3PM UTC - for certainity 15:30
        return utc.replace(hour=15, minute=30, second=0, microsecond=0)

    @staticmethod
    def stamp_valid_to(utc):
        # fixer.io = The rates are updated daily around 4PM CET.
        # = valid for one day
        return utc.shift(days=+1, seconds=-1)

    def latest_rates_update(self, utc_now=None):
        return self.__class__.latest_rates_update(utc_now=utc_now)

    @classmethod
    def latest_rates_update(cls, utc_now=None):

        if utc_now is None:
            utc_now = arrow.utcnow()

        today_update_hour = cls.stamp_time(utc_now)
        if today_update_hour > utc_now:
            update_time = today_update_hour.shift(days=-1)
        else:
            update_time = today_update_hour

        return update_time

    @classmethod
    def new_rates_available(cls, utc_db_valid_to, utc_now=None):
        latest_rates_update = cls.latest_rates_update(utc_now)
        prinf('%s site', cls.name)
        prinf('%s latest_rates_update', latest_rates_update)
        prinf('%s db_valid_to', utc_db_valid_to)
        if latest_rates_update <= utc_db_valid_to:
            # old data are latest - no new request needed
            return False, latest_rates_update
        else:
            # new rates available
            return True, latest_rates_update


    def start(self):
        self.start_time = time.time()
    def end(self):
        prinf('%s sec', time.time() - self.start_time)

    def get_response(self):
        prinf('%s params: %s', self.base_url, self.my_params)
        self.start()
        self.response = requests.get(self.base_url, params=self.my_params)
        self.end()

        if not self.response:
            prinf(self.response)
            return None
        else:
            if self.response.status_code > 400 :
                prinw('%s currency converter site response not found. %s', self.name, self.response.status_code)
                return None
            elif self.response.status_code == 200:
                prinf('%s response ok', self.name)

        self.in_ccode = self.response.json()[self.strs[jpn.key_in_ccode]]
        self.stamp_datetime()

        self.rates = self.response.json()[self.strs[jpn.key_output]]
        self.rates.update({self.in_ccode: float(1)})

    def get_this_rate_for_ccode(self, in_ccode, out_ccode, start_params={}):
        self.my_params = start_params
        self.create_url()
        self.update_params(in_ccode=in_ccode, out_ccode=out_ccode)
        self.get_response()

    def get_all_rates_for_ccode(self, in_ccode, my_params={}):
        self.my_params = start_params
        self.create_url()
        self.update_params(in_ccode=in_ccode)
        self.get_response()

    def get_all_rates(self):
        self.create_url()
        self.get_response()