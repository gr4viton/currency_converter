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


class CurrencyConverterSiteCurrencylayer():
    """Free currency conversion site apilayer with Api interface class

    merge of sites currencylayer and
    """

    name = 'apilayer'

    def __init__(self):
        self.init_site_specifications()

        self.my_params = None
        self.rates = None

        self.valid_from_utc = None
        self.valid_to_utc = None

        self.timeout = 1  # url response timeout in seconds
        self.in_ccode = None
        self.responded = False

    def init_site_specifications(self):
        self.name = 'apilayer'
        self.base = 'http://www.apilayer.net/api/'
        self.strs = {
            jpn.var_in_ccode: 'from',
            jpn.var_out_ccode: 'to',
            jpn.path_latest: 'historical',
            jpn.var_date: 'date',
            jpn.var_date_format: 'YYYY-MM-DD',
            jpn.key_date: 'timestamp',
            jpn.key_date_format: 'X',  # arrow timestamp format
            jpn.key_in_ccode: 'source',
            jpn.key_output: 'quotes',
            jpn.var_apikey: 'access_key',
            jpn.free_apikey: 'f97e97072345994b708fb559a09788a5',
        }

    def create_url(self):
        """Appends latest rates suffix to base_url"""
        self.base_url = self.base + self.strs[jpn.path_latest]


    def update_params(self, in_ccode, out_ccode=None):
        """Update request parameters"""
        self.my_params.update({self.strs[jpn.var_in_ccode]: in_ccode})
        if out_ccode:
            self.my_params.update({self.strs[jpn.var_out_ccode]: out_ccode})

        # add free apikey
        self.my_params.update({self.strs[jpn.var_apikey]: self.strs[jpn.free_apikey]})

        # as free apikey gives only one day old data we must add date specification
        date = arrow.utcnow().shift(days=-1)
        date_str = date.format(self.strs[jpn.var_date_format])
        self.my_params.update({self.strs[jpn.var_date]: date_str})

    def update_rates_valid_data(self):
        """Updates validation utc times from site response cet time"""
        date_cet = str(self.response_data.json()[self.strs[jpn.key_date]])
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

        The rates are updated every hour for the free plan at currencylayer.com
        """
        return utc.replace(minute=0, second=0, microsecond=0)

    @staticmethod
    def stamp_valid_to(utc):
        """Adds valid_to time - as currencylayer.com rates are valid for one hour

        minus one second for no overlapping"""
        return utc.shift(hours=+1, seconds=-1)

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

        return True

    def preprocess_rates(self):
        """Converts the acquired rates json dictionary data into common format

         {
         out_ccode : float(amount)
         ...
         }
        """
        # as the data are in this format
        # {
        #   ''.join([in_ccode, out_ccode]) : float(amount)
        # }
        # we must preprocess_rates
        self.rates = {key[3:]: value for key, value in self.rates.items()}

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
        self.preprocess_rates()
        return self.response_success