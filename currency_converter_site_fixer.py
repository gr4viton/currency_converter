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


class CurrencyConverterSiteFixer(CurrencyConverterSite):
    """Free currency conversion site fixer.io with Api interface class"""
    name = 'fixer'

    def __init__(self):
        """Initializes all needed parameters for Fixer site"""
        CurrencyConverterSite.__init__(self,
            'fixer',
            'http://api.fixer.io/',
            {
                jpn.key_output: 'rates',
                jpn.key_in_ccode: 'base',
                jpn.var_in_ccode: 'base',
                jpn.var_out_ccode: 'symbols',
                jpn.path_latest: 'latest',
                jpn.key_date: 'date',
                jpn.key_date_format: 'YYYY-MM-DD',
            }
        )

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

    def preprocess_rates(self):
        """Converts the acquired rates json dictionary data into common format

         {
         out_ccode : float(amount)
         ...
         }
        """
        # the rates from fixar.io are almost exactly in the required common format
        # as requested ccode is not in the request respond
        # we add it => e.g 1 EUR = 1 EUR => needed for further pandas extrapolation
        self.rates.update({self.in_ccode: float(1)})
