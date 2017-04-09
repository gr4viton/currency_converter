import arrow
import requests
import time
import logging

from logging import info as prinf
from logging import debug as prind
from logging import warning as prinw
from logging import error as prine

from parameter_names_enums import JsonParameterNames as jpn

class CurrencyConverterSiteApilayer():

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
            jpn.key_output: 'rate',
            jpn.var_in_ccode: 'from',
            jpn.var_out_ccode: 'to',
            jpn.path_latest: 'historical',
            jpn.var_date: 'date',
            jpn.var_date_format: 'YYYY-MM-DD',
            jpn.var_apikey: 'access_key',
            jpn.free_apikey: 'f97e97072345994b708fb559a09788a5',
        }
