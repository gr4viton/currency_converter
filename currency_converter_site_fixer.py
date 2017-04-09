import arrow
import requests
import time
import logging

from logging import info as prinf
from logging import debug as prind
from logging import warning as prinw
from logging import error as prine

from currency_converter_site import CurrencyConverterSite
from parameter_names_enums import JsonParameterNames as jpn

from global_timer import g_start, g_end

class CurrencyConverterSiteFixer(CurrencyConverterSite):
    name = 'fixer'

    def __init__(self):
        self.init_site_specifications()

        self.my_params = None  # parameters for site requests
        self.rates = None  # exchange rates from the site
        self.timeout = 1  # url response timeout in seconds

        # retrieved rates validity
        self.valid_from_utc = None
        self.valid_to_utc = None

        self.in_ccode = None
        self.response_success = False

    def init_site_specifications(self):
        self.name = 'fixer'
        self.base = 'http://api.fixer.io/'
        self.strs = {
            jpn.key_output: 'rates',
            jpn.key_in_ccode: 'base',
            jpn.var_in_ccode: 'base',
            jpn.var_out_ccode: 'symbols',
            jpn.path_latest: 'latest',
            jpn.key_date: 'date',
            jpn.key_date_format: 'YYYY-MM-DD',
        }

    def create_url(self):
        self.base_url = self.base + self.strs[jpn.path_latest]

    def update_params(self, in_ccode, out_ccode=None):
        self.my_params.update({self.strs[jpn.var_in_ccode] : in_ccode})
        if out_ccode:
            self.my_params.update({self.strs[jpn.var_out_ccode] : out_ccode})

    def update_rates_valid_data(self):
        date_cet = self.response_data.json()[self.strs[jpn.key_date]]
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

    @classmethod
    def get_site_last_updated(cls, utc_now=None):
        if utc_now is None:
            utc_now = arrow.utcnow()

        today_update_hour = cls.stamp_time(utc_now)
        if today_update_hour > utc_now:
            update_time = today_update_hour.shift(days=-1)
        else:
            update_time = today_update_hour

        return update_time

    def refresh_last_updated(self, utc_now=None):
        self.last_updated = self.__class__.get_site_last_updated(utc_now)

    def fresher_than_db(self, utc_db_valid_from):
        return self.last_updated > utc_db_valid_from

    def acquire_rates_data(self):
        prinf('%s params: %s', self.base_url, self.my_params)
        g_start()
        try:
            self.response_data = requests.get(self.base_url, params=self.my_params, timeout=self.timeout)
        except OSError:
            prinw('%s host not available', self.name)
            return False
        g_end('request responded')

        if not self.response_data:
            return False
        else:
            status_code = self.response_data.status_code
            prinf(status_code )
            if status_code > 400 :
                prinw('%s currency converter site response not found. %s', self.name, status_code)
                return False
            elif status_code == 200:
                prinf('%s response ok', self.name)

        self.in_ccode = self.response_data.json()[self.strs[jpn.key_in_ccode]]
        
        self.update_rates_valid_data()

        self.rates = self.response_data.json()[self.strs[jpn.key_output]]

        # as requested ccode is not in the request respond
        # we add it => e.g 1 EUR = 1 EUR => needed for further pandas extrapolation
        self.rates.update({self.in_ccode: float(1)})

        return True

    def get_all_rates(self):
        self.create_url()
        self.response_success = self.acquire_rates_data()
        return self.response_success

    def get_one_rate_for_ccode(self, in_ccode, out_ccode, start_params={}):
        self.my_params = start_params
        self.create_url()
        self.update_params(in_ccode=in_ccode, out_ccode=out_ccode)
        self.get_response()

    def get_all_rates_for_ccode(self, in_ccode, my_params={}):
        self.my_params = start_params
        self.create_url()
        self.update_params(in_ccode=in_ccode)
        self.get_response()