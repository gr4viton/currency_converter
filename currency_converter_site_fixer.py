import arrow
import requests
import time
import logging

from logging import info as prinf
from logging import debug as prind
from logging import warning as prinw
from logging import error as prine

from parameter_names_enums import JsonParameterNames as jpn

from global_timer import g_start, g_end


class CurrencyConverterSiteFixer():
    """Free currency conversion site fixer.io with Api interface class"""
    name = 'fixer'

    def __init__(self):
        """Initializes all needed parameters for Fixer site"""
        self._init_site_specifications_()

        self.my_params = None  # parameters for site requests
        self.rates = None  # exchange rates from the site
        self.timeout = 1  # url response timeout in seconds

        # retrieved rates validity
        self.valid_from_utc = None
        self.valid_to_utc = None

        self.in_ccode = None
        self.response_success = False

    def _init_site_specifications_(self):
        """Initializes site specification strings for Fixer site"""
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
        """Appends latest rates suffix to base_url"""
        self.base_url = self.base + self.strs[jpn.path_latest]

    def update_params(self, in_ccode, out_ccode=None):
        """Update request parameters"""
        self.my_params.update({self.strs[jpn.var_in_ccode]: in_ccode})
        if out_ccode:
            self.my_params.update({self.strs[jpn.var_out_ccode]: out_ccode})

    def update_rates_valid_data(self):
        """Updates validation utc times from site response cet time"""
        date_cet = self.response_data.json()[self.strs[jpn.key_date]]
        fmt = self.strs[jpn.key_date_format]
        date_time = arrow.get(date_cet, fmt)
        self.valid_from_utc = self.__class__.stamp_time(date_time)
        self.valid_to_utc = self.__class__.stamp_valid_to(self.valid_from_utc)

        prinf('%s valid_from_utc', self.valid_from_utc)
        prinf('%s valid_to_utc', self.valid_to_utc)
        prinf('%s now', arrow.utcnow())

    @staticmethod
    def stamp_time(utc):
        """Adds time in day of the update

        The rates are updated daily around 4PM CET @ fixer.io
        Central European Time is 1 hour ahead of Coordinated Universal Time
        = 3PM UTC - for certainity 15:30
        """
        return utc.replace(hour=15, minute=30, second=0, microsecond=0)

    @staticmethod
    def stamp_valid_to(utc):
        """Adds valid_to time - as fixer.io rates are valid for one day

        minus one second for no overlapping"""
        return utc.shift(days=+1, seconds=-1)

    @classmethod
    def get_site_last_updated(cls, utc_now=None):
        """Returns utc time of latest update on the site relative to current utc time"""
        if utc_now is None:
            utc_now = arrow.utcnow()

        today_update_hour = cls.stamp_time(utc_now)
        if today_update_hour > utc_now:
            update_time = today_update_hour.shift(days=-1)
        else:
            update_time = today_update_hour

        return update_time

    def refresh_last_updated(self, utc_now=None):
        """Updates [last_updated] utc time"""
        self.last_updated = self.__class__.get_site_last_updated(utc_now)

    def fresher_than_db(self, utc_db_valid_from):
        """Returns True if this site has fresher data then the database"""
        return self.last_updated > utc_db_valid_from

    def acquire_rates_data(self):
        """Request rates data from the site and processes them

        returns True on successful receiving and data processing
        """
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
                prinw('%s currency converter site response not found. %s', self.nam, status_code)
                return False
            elif status_code == 200:
                prinf('%s response ok', self.name)

        self.update_rates_valid_data()
        self.in_ccode = self.response_data.json()[self.strs[jpn.key_in_ccode]]

        self.rates = self.response_data.json()[self.strs[jpn.key_output]]

        # as requested ccode is not in the request respond
        # we add it => e.g 1 EUR = 1 EUR => needed for further pandas extrapolation
        self.rates.update({self.in_ccode: float(1)})
        return True

    def get_all_rates(self, in_ccode=None, out_ccode=None, req_params_dict={}):
        """Requests and acquires all rates data from the site

        - if no in_ccode nor out_ccode is specified - requests all rates for site base currency
        - if no out_ccode is specified - requests all rates for the in_ccode currency
        - if both in_ccode and out_ccode is specified - requests site rate for these currencies

        returns - True on success, False otherwise
        """
        self.my_params = req_params_dict
        self.create_url()
        self.update_params(in_ccode=in_ccode, out_ccode=out_ccode)
        self.response_success = self.acquire_rates_data()
        return self.response_success