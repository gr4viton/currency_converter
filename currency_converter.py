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
from sqlalchemy import create_engine

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

from currency_converter_site import CurrencyConverterSite
from currency_converter_site_fixer import CurrencyConverterSiteFixer

#class CurrencyConverterSiteApilayer(CurrencyConverterSite):



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

        self.db_engine_path = 'sqlite:///db\\exchange_rates.db'
        self.db_file = 'db/exchange_rates.db'
        self.rates_table_name = 'rates'
        self.rates_info_table_name = 'rates_info'

        self.sites_file = 'sites.pickle'

        self.in_amount = amount
        self.in_currency = input_cur
        self.out_currency = output_cur
        self.in_code = self.out_code = None

        self.init_cc_sites()
        self.update_rates_data()

    def init_cc_sites(self):
        self.sites = []
        self.init_curconv_site_fixer()
        #self.init_curconv_site_apilayer()

        #self.sites = {ccs.name : ccs for ccs in self.site_list}

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
            jpn.key_date: 'date',
            jpn.key_date_format: 'YYYY-MM-DD',
        }

        # The rates are updated daily around 4PM CET.
        fixer = CurrencyConverterSiteFixer('fixer',
                                      base='http://api.fixer.io/',
                                      strs=fixer_strs
                                      )
        self.sites.append(fixer)


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


    def request_sites_from_net(self, sites=None):

        if sites is None:
            sites = self.sites
        elif type(sites) is not list:
            sites = [sites]

        [ site.get_all_rates() for site in sites]


    def load_sites_from_pickle(self):
        if Path(self.sites_file).is_file():
            with open(self.sites_file, 'rb') as input:
                self.sites = pickle.load(input)
            print(self.sites_file, 'loaded')
            print(self.sites)
        else:
            self.request_sites_from_net()

            print(self.sites)
            with open(self.sites_file, 'wb') as output:
                pickle.dump(self.sites, output, pickle.HIGHEST_PROTOCOL)
            print(self.sites_file, 'saved')


    def rates_to_pandas(self, sites=None):
        # take rates data from the most recent site
        if sites is None:
            sites = self.sites
        elif type(sites) is not list:
            sites = [sites]

        for site in sites:

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

            #print(df)
            self.rates_df = df

            self.rates_info_df = pd.DataFrame({'source': site.name,
                                               'valid_from_utc': str(site.valid_from_utc),
                                               'valid_to_utc': str(site.valid_to_utc),
                                               'base_ccode': base}, index=[0])


    def save_to_sql(self):
        with self.engine.connect() as conn, conn.begin():
            self.rates_df.to_sql(self.rates_table_name, conn, if_exists='replace')

            self.rates_info_df.to_sql(self.rates_info_table_name, conn, if_exists='replace')

            print('Saved to database:\n', self.rates_info_df)

    def update_rates_data(self):

        if not Path(self.db_file).is_file():
            # create empty database file
            open(self.db_file, 'a').close()

        if Path(self.db_file).is_file():
            self.engine = create_engine(self.db_engine_path)
            if not self.engine.dialect.has_table(self.engine, self.rates_info_table_name):
                # no saved data - need to get them and save to sql
                self.request_sites_from_net()
                self.rates_to_pandas()
                self.save_to_sql()

            else:
                # database rates exist - find out if we need to request new data
                with self.engine.connect() as conn, conn.begin():
                    # find out database valid_to
                    db_rates_info_df = pd.read_sql_table(self.rates_info_table_name, self.engine)
                    print('loaded database:\n', db_rates_info_df)
                    db_valid_to_str = str(db_rates_info_df['valid_to_utc'][0])
                    db_valid_to = arrow.get(db_valid_to_str)

                    print(arrow.utcnow(), 'utc_now')
                    utc_now = arrow.utcnow().shift(days=+12, hours=+4)
                    print(utc_now, 'simulated utc_now')

                    update_need_and_time = [
                        site.__class__.new_rates_available(utc_db_valid_to=db_valid_to,
                                                           utc_now=utc_now) for site in self.sites]
                    update_needed, latest_update = zip(*update_need_and_time)
                    print(update_needed, latest_update )
                    if any(update_needed):
                        if len(latest_update) > 1:
                            # more sites - get the latest update
                            _, index = max(latest_update)
                            print(index)
                        else:
                            index = 0

                        actual_site = self.sites[index]
                        self.request_sites_from_net(actual_site)
                        self.rates_to_pandas(actual_site)
                        self.save_to_sql()
                    # for site_date in site_dates:
                    #site_dates, db_date
                # load

                # update data

        else:
            print("""Offline database file is not present, even after creation attempt."""
                  """\nPlease create empty file in this path:'""", Path(self.db_file),
                  """\nWorking without offline database can be slow - for every request there is internet connection needed""")


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
