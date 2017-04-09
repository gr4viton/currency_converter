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
from currency_converter_site import CurrencyConverterSite

class CurrencyConverterSiteCurrencylayer(CurrencyConverterSite):
    """Free currency conversion site apilayer with Api interface class

    merge of sites currencylayer and
    """

    name = 'apilayer'

    def __init__(self):
        CurrencyConverterSite.__init__(self,
            'apilayer',
            'http://www.apilayer.net/api/',
            {
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
        )



    def update_additional_params(self):
        # add free apikey
        self.my_params.update({self.strs[jpn.var_apikey]: self.strs[jpn.free_apikey]})

        # as free apikey gives only one day old data we must add date specification
        date = arrow.utcnow().shift(days=-1)
        date_str = date.format(self.strs[jpn.var_date_format])
        self.my_params.update({self.strs[jpn.var_date]: date_str})


    @staticmethod
    def stamp_time(utc):
        """Adds time in day of the update

        The rates are updated every hour for the free plan at currencylayer.com
        """
        utc = utc.replace(minute=0, second=0, microsecond=0)
        utc = utc.shift(hours=-1)  # not sure if because CET-UTC or DST - not mentioned on their pages FAQ
        return utc

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
            update_time = today_update_hour.shift(hours=-1)
        else:
            update_time = today_update_hour

        return update_time

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
