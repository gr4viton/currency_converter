#!/usr/bin/python
# task assignment here:
# https://gist.github.com/MichalCab/3c94130adf9ec0c486dfca8d0f01d794


import redis

import requests
import json
#import BeautifulSoup
import sys
import getopt

import arrow # better then time
import sqlite3
import pandas as pd
pd.options.display.max_rows = 20

import pickle # dev
from pathlib import Path

#TODO
# [x] class like
# [] use decorators
# [] multiple currencies have similar symbols = decision tree - http://www.xe.com/symbols.php
# [] use pandas
# [] use redis - second program with interprogram communication

# [] more prices
# [] graph?
# []
# [] vanila vs updated getopt function
# [] one commit - in master branch - multiple in other branches

# [] currency signes vs symbols vs names

# [] otestovat funkcnost
# [] asserty
# [] unit test??

# [] print to syserr - decorator??

# [] localisation

# [] time effectivity!!! - measurement - argument = fast or robust

# [] suggest the nearest textually? - parameter for automatic nearest suggestion conversion

# [] have offline database for case without connection !

#OUTPUT = json with following structure:
#{
#    "input": {
#         "amount": <float>,
#         "currency": <3 letter currency code>
#     }
#     "output": {
#         <3 letter currency code>: <float>
#     }
# }

from json_enum import JsonParameterNames as jpn

#class CurrencyConverterSiteApilayer(CurrencyConverterSite):

class CurrencyConverterSite():
    def __init__(self, name, base, strs):
        self.name = name
        self.base = base
        self.strs = strs

    def create_url(self):
        pass

    def create_params(self):
        pass

    def get_response(self):
        pass

    def get_this_rate_for_ccode(self, in_ccode, my_params={}):
        pass

    def get_these_rates_for_ccode(self, in_ccode, my_params={}):
        pass

    def get_all_rates_for_ccode(self, in_ccode, my_params={}):
        pass

    def get_rates_for(self, in_ccode, my_params={}):
        self.base_url = self.base

        def _add_path_(try_jpn):
            part = self.strs.get(try_jpn, None)
            if part:
                self.base_url += part
                return True
            return False

        def _add_param_(try_jpn, var=None, set_jpn=None):
            part = self.strs.get(try_jpn, None)
            if part:
                if not var:
                    var = part
                if not set_jpn:
                    set_jpn = try_jpn
                my_params.update({self.strs[set_jpn] : var})
                return True
            return False

        _add_path_(jpn.path_latest)

        my_params.update({self.strs[jpn.var_in_ccode] : in_ccode})

        if self.strs.get(jpn.var_apikey, None):
            if not _add_param_(jpn.paid_apikey, set_jpn=jpn.var_apikey):
                _add_param_(jpn.free_apikey, set_jpn=jpn.var_apikey)


        if _add_param_(jpn.var_date):
            curdate = arrow.now().format(self.strs[jpn.var_date_format])
            print(curdate)
            _add_param_(jpn.var_date, var=curdate)
            pass

        # get server output
        print(self.base_url, my_params)
        response = requests.get(self.base_url, params=my_params)

        if not response:
            print(response)
            return None
        else:
            if response.status_code > 400 :
                print(self.name, 'currency converter site response not found. ', response.status_code)
                return None
            elif response.status_code == 200:
                print(response.json())


        results = response.json()[self.strs[jpn.key_output]]
        self.output = [in_ccode, results]
        return self.output


    def get_some_rates_for(self, in_ccode, out_ccode_str, my_params={}):
        my_params.update({self.strs[jpn.var_out_ccode] : out_ccode_str})
        return self.get_rates_for(in_ccode, my_params=my_params)


    # def __str__(self):
    #     text =
    #     return text
    #


class CurrencyConverterFixer(CurrencyConverterSite):

    def __init__(self, name, base, strs):
        self.name = name
        self.base = base
        self.strs = strs
        self.my_params = None
        self.rates = None

    def create_url(self):
        self.base_url = self.base + self.strs[jpn.path_latest]

    def update_params(self, in_ccode, out_ccode=None):
        self.my_params.update({self.strs[jpn.var_in_ccode] : in_ccode})
        if out_ccode:
            self.my_params.update({self.strs[jpn.var_out_ccode] : out_ccode})

    def get_response(self):
        print(self.base_url, self.my_params)
        self.response = requests.get(self.base_url, params=self.my_params)

        if not self.response:
            print(self.response)
            return None
        else:
            if self.response.status_code > 400 :
                print(self.name, 'currency converter site response not found. ', self.response.status_code)
                return None
            elif self.response.status_code == 200:
                print(self.name, 'response ok')

        self.in_ccode = self.response.json()[self.strs[jpn.key_in_ccode]]
        self.other_rates = self.response.json()[self.strs[jpn.key_output]]
        self.rates = self.other_rates
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

class CurrencyConverter():
    currency_codes = {'Kc': 'CZK'}
    currency_servers = ['http://www.xe.com/symbols.php']

    strs = {jpn.key_input: 'input',
            jpn.key_in_amount: 'amount',
            jpn.key_in_ccode: 'currency',
            jpn.key_output: 'output'}

    def __init__(self, amount, input_cur, output_cur):

        amount = 10
        input_cur = 'CZK'
        output_cur = 'EUR'

        self.db_file = 'db/exchange_rates.db'
        self.table_name = 'rates'
        self.db = None

        self.in_amount = amount
        self.in_currency = input_cur
        self.out_currency = output_cur
        self.in_code = self.out_code = None

        self.init_cc_sites()
        self.update_rates_data()

    def init_cc_sites(self):
        self.site_list = []
        self.init_curconv_site_fixer()
        #self.init_curconv_site_apilayer()

        self.sites = {ccs.name : ccs for ccs in self.site_list}

        in_ccode = 'CZK'
        #out_ccode_str = 'EUR,USD'
        out_ccode_str = 'EUR'



    def init_curconv_site_fixer(self):

        fixer_strs = {
            jpn.key_output: 'rates',
            jpn.key_in_ccode: 'base',
            jpn.var_in_ccode: 'base',
            jpn.var_out_ccode: 'symbols',
            jpn.path_latest: 'latest',
        }

        # The rates are updated daily around 4PM CET.
        fixer = CurrencyConverterFixer('fixer',
                                      base='http://api.fixer.io/',
                                      strs=fixer_strs
                                      )
        self.site_list += [fixer]


    def init_curconv_site_apilayer(self):

        apilayer_strs = {
            jpn.key_output: 'rate',
            jpn.var_in_ccode: 'from',
            jpn.var_out_ccode: 'to',
            jpn.path_latest: 'historical',
            jpn.var_date: 'date',
            jpn.var_date_format: 'YYYY-MM-DD',
            jpn.var_apikey: 'access_key',
            jpn.free_apikey: 'f97e97072345994b708fb559a09788a5',
        }
        apilayer = CurrencyConverterSite('apilayer',
                                          base='http://www.apilayer.net/api/',
                                          strs=apilayer_strs )
        self.site_list += [apilayer]


    def query_db(self, query, args=(), one=False):
        cur = self._get_db_().execute(query, args)
        rv = cur.fetchall()
        cur.close()
        return (rv[0] if rv else None) if one else rv

    def _get_db_(self):
        if self.db is None:
            self._db_connect_()
        return self.db

    def _db_connect_(self):
        self.db = sqlite3.connect(self.db_file)

    def update_rates_data(self):


        # consult the database
        #event = self.query_db('CREATE TABLE IF NOT EXISTS {} (id string)'.format(self.table_name))
        #self._get_db_().commit()
        #a = self.query_db('SELECT * FROM {};'.format(self.table_name))

        sites_file = 'sites.pickle'
        if Path(sites_file).is_file():
            with open(sites_file, 'rb') as input:
                self.sites = pickle.load(input)
            print(sites_file, 'loaded')
            print(self.sites)
        else:
            # get all the online data
            [ site.get_all_rates() for site in self.sites.values()]

            print(self.sites)
            with open(sites_file, 'wb') as output:
                pickle.dump(self.sites, output, pickle.HIGHEST_PROTOCOL)
            print(sites_file, 'saved')


        # save data
        for site in self.sites.values():
            base = site.in_ccode
            ccodes_rates = [(key, site.rates[key]) for key in sorted(site.rates.keys())]
            ccodes, rates = zip(*ccodes_rates)

            df = pd.DataFrame({base: rates})
            df.index = ccodes

            digits = 4
            # calculate other values from base column - round digits
            for col_ccode in ccodes:
                if col_ccode != base:
                    col = [round(df[base].loc[row_ccode] / df[base].loc[col_ccode], digits) for row_ccode in ccodes]
                    df[col_ccode] = col



    def init_currency_codes(self):
        pass

    @staticmethod
    def get_currency_code(currency):
        currency = currency.upper()
        if currency in CurrencyConverter.currency_codes.values():
            return currency
        else:
            return CurrencyConverter.currency_codes.get(currency, None)

    def convert_symbols(self):
        self.in_code = CurrencyConverter.get_currency_code(self.in_currency)
        if self.in_code is None:
            print('Currency symbol [{}] is not in our database.'.format(self.in_currency), file=sys.stderr)
            # suggest the nearest textually?
            sys.exit(2)

        self.out_code = CurrencyConverter.get_currency_code(self.out_currency)

    def convert(self):
        # connected to internet?
        # start redis if not running
        #
        #
        self.convert_symbols()

        self.in_code = 'CZK'
        self.out_code = 'EUR'
        self.out_amount = 1.0
        self.print_json()


    #def get_exchange_rates(self):


    def print_json(self):
        self.out_dict = {self.strs[jpn.key_input]: { self.strs[jpn.key_in_amount] : float(self.in_amount),
                                                       self.strs[jpn.key_in_ccode] : self.in_code },
                         self.strs[jpn.key_output] : { self.out_code : float(self.out_amount) }
                         }
#        print(json.dump(self.out_dict))
        print(self.out_dict)


def parse_arguments(argv):
    amount = None
    input_cur = None
    output_cur = None

    help_text = """test.py --amount <float_amount> --input_currency <currency_symbol> """ + \
                """(--output_currency <currency_symbol>)"""

    try:
        opts, args = getopt.getopt(argv,'h:a:i:o:', ['help=','amount=', 'input_currency=', 'output_currency='])
    except getopt.GetoptError:
        print(help_text)
        sys.exit(2)

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            print(help_text)
            sys.exit()
        elif opt in ('-a', '--amount'):
            amount = arg
        elif opt in ('-i', '--input_currency'):
            input_cur = arg
        elif opt in ('-o', '--output_currency'):
            output_cur = arg

    return amount, input_cur, output_cur

if __name__ == '__main__':
   params = parse_arguments(sys.argv[1:])
   cc = CurrencyConverter(*params)
  # cc.convert()
