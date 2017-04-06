#!/usr/bin/python
# -*- coding: utf-8 -*-
# task assignment here:
# https://gist.github.com/MichalCab/3c94130adf9ec0c486dfca8d0f01d794

import redis

import requests
import json
#import BeautifulSoup

import sys

import argparse

import time

import arrow # better then time
from sqlalchemy import create_engine

import pandas as pd
pd.options.display.max_rows = 20

import pickle # dev
from pathlib import Path

import logging
#logging.basicConfig(filename='run.log', filemode='w', level=logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)

from logging import info as prinf
from logging import debug as prind
from logging import warning as prinw
from logging import error as prine


#TODO
# [x] class like
# [x] use decorators
# [n] multiple currencies have similar symbols = decision tree - http://www.xe.com/symbols.php
# [x] use pandas
# [] use redis - second program with interprogram communication
# - expire time - to the next update from any site

# [n] more prices
# [n] graph?

# [n] vanila vs updated getopt function
# [] one commit - in master branch - multiple in other branches

# [x] currency signes vs symbols
# [n] vs names

# [] otestovat funkcnost
# [] asserty
# [] unit test?? - nose2 module

# [x] prinf to syserr - logger

# [] localisation

# [] time effectivity!!! - measurement - argument = fast or robust

# [] suggest the nearest textually? - parameter for automatic nearest suggestion conversion

# [x] have offline database for case without connection !

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

# [] save next update as a cron - updates automatically not needed to check
# [] save latest update time to file instead of database - quicker load - but what about redis

from json_enum import JsonParameterNames as jpn

from currency_converter_site import CurrencyConverterSite
from currency_converter_site_fixer import CurrencyConverterSiteFixer
from currency_symbol_converter import CurrencySymbolConverter
#class CurrencyConverterSiteApilayer(CurrencyConverterSite):





class CurrencyConverter():
    currency_servers = ['http://www.xe.com/symbols.php']

    strs = {jpn.key_input: 'input',
            jpn.key_in_amount: 'amount',
            jpn.key_in_ccode: 'currency',
            jpn.key_output: 'output'}

    def __init__(self, amount, input_cur, output_cur):
        #redis port = 6379
        self.db_engine_path = 'sqlite:///db\\exchange_rates.db'
        self.db_file = 'db/exchange_rates.db'
        self.rates_table_name = 'rates'
        self.rates_info_table_name = 'rates_info'

        self.sites_file = 'sites.pickle'

        self.in_amount = amount
        self.in_currency = input_cur

        self.out_currency = output_cur
        self.out_amount = None
        self.in_code = None
        self.out_code = None
        self.digits = 4

        self.r = redis.StrictRedis()
        self.csc = CurrencySymbolConverter(self.r)

        self.init_cc_sites()
        self.update_rates_data()


    def init_cc_sites(self):
        self.sites = []
        self.init_curconv_site_fixer()

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

        [site.get_all_rates() for site in sites]


    def load_sites_from_pickle(self):
        if Path(self.sites_file).is_file():
            with open(self.sites_file, 'rb') as input:
                self.sites = pickle.load(input)
            prinf('%s loaded', self.sites_file)
            prinf(self.sites)
        else:
            self.request_sites_from_net()

            prinf(self.sites)
            with open(self.sites_file, 'wb') as output:
                pickle.dump(self.sites, output, pickle.HIGHEST_PROTOCOL)
            prinf('%s saved', self.sites_file)

    def sites_to_pandas(self, sites=None, latest=None):
        # take rates data from the most recent site
        if sites is None:
            sites = self.sites
        elif type(sites) is not list:
            sites = [sites]

        if latest:
            latest_updates = [site.valid_from_utc for site in sites]
            if len(latest_updates) > 1:
                # more sites - get the latest update
                _, idx = max(latest_updates)
                #prinf(index)
            else:
                idx = 0

            sites = [self.sites[idx]]

        for site in sites:

            base = site.in_ccode
            ccodes_rates = [(key, site.rates[key]) for key in sorted(site.rates.keys())]
            ccodes, rates = zip(*ccodes_rates)

            df = pd.DataFrame({base: rates})
            #df[0] = ccodes
            df.index = ccodes
            #df['ccodes'] = ccodes
            #print('as')
            #df.set_index(index)
            #df.set_index([str(ccode) for ccode in ccodes])
            #prinf('ccodes type %s', type(ccodes[1]))




            # calculate other values from base column - do not round digits
            for col_ccode in ccodes:
                if col_ccode != base:
                    col = [df[base].loc[row_ccode] / df[base].loc[col_ccode] for row_ccode in ccodes]
                    col = [round(df[base].loc[row_ccode] / df[base].loc[col_ccode], 4) for row_ccode in ccodes]
                    df[col_ccode] = col

            self.rates_df = df
            self.rates_info_df = pd.DataFrame({'source': site.name,
                                               'valid_from_utc': str(site.valid_from_utc),
                                               'valid_to_utc': str(site.valid_to_utc),
                                               'base_ccode': base}, index=[1])

    def save_to_sql(self):
        with self.engine.connect() as conn, conn.begin():
            self.rates_df.to_sql(self.rates_table_name, conn, if_exists='replace')

            self.rates_info_df.to_sql(self.rates_info_table_name, conn, if_exists='replace')

            prinf('Saved to database:\n%s', self.rates_info_df)



    def start(self):
        self.start_time = time.time()

    def end(self):
        prinf('%s sec', time.time() - self.start_time)

    def db_file_exist(self):
        return Path(self.db_file).is_file()

    def sql_to_pandas(self, in_ccode=None, out_ccode=None):
        if self.db_file_exist():
            self.engine = create_engine(self.db_engine_path)
            rates_table_exist = self.engine.dialect.has_table(self.engine, self.rates_table_name)
            if rates_table_exist:

                if not (in_ccode or out_ccode):
                    self.start()
                    # load whole database to pandas (time consuming)
                    self.rates_df = pd.read_sql_table(self.rates_table_name, self.engine)
                    self.end()
                    #prinf('loaded database:\n%s', self.rates_df)
                else:
                    pass


    def update_rates_data(self):
        if not self.db_file_exist():
            # create empty database file
            open(self.db_file, 'a').close()

        if self.db_file_exist():
            self.engine = create_engine(self.db_engine_path)

            # possible not use database for loading rates_info_table_exist = use file
            #rates_info_txt_exist = self.Path(self.rates_info_txt_file)
            #if rates_info_txt_exist:

            rates_info_table_exist = self.engine.dialect.has_table(self.engine, self.rates_info_table_name)
            if not rates_info_table_exist:
                # need to get data from the internet
                self.request_sites_from_net()
                self.sites_to_pandas()
                # store them to database
                self.save_to_sql()
            else:
                # database rates exist
                # - find out if we need to request new data
                with self.engine.connect() as conn, conn.begin():
                    self.start()
                    # find out database valid_to
                    db_rates_info_df = pd.read_sql_table(self.rates_info_table_name, self.engine)
                    self.end()
                    prinf('loaded database:\n%s', db_rates_info_df)
                    db_valid_to_str = str(db_rates_info_df['valid_to_utc'][0])
                    db_valid_to = arrow.get(db_valid_to_str)

                    # simulating different time
                    utc_now = arrow.utcnow()
                    prinf('%s utc_now', utc_now)
                    #utc_now = utc_now.shift(days=+12, hours=+4)
                    prinf('%s simulated utc_now', utc_now)

                    # which sites can give us later rates then the ones saved in database
                    update_need_and_time = [
                        site.__class__.new_rates_available(utc_db_valid_to=db_valid_to,
                                                           utc_now=utc_now) for site in self.sites]
                    update_needed, latest_updates = zip(*update_need_and_time)

                    prinf('update needed in sites:\n%s\nlatest_update dates:\n%s', update_needed, latest_updates )

                    if any(update_needed):
                        if len(latest_updates) > 1:
                            # more sites - get the latest update
                            _, idx = max(latest_updates)
                            prinf(idx)
                        else:
                            idx = 0

                        actual_site = self.sites[idx]
                        self.request_sites_from_net(actual_site)
                        self.sites_to_pandas(actual_site)
                        self.save_to_sql()
                # load

                # update data

        else:
            prinw("""Offline database file is not present, even after creation attempt."""
                  """\nPlease create empty file in this path: <%s>"""
                  """\nWorking without offline database can be slow - for every request there is internet connection needed"""
                  , str(Path(self.db_file)))



    def convert_to_ccode(self):
        self.in_code = self.csc.get_currency_code(self.in_currency)
        if self.in_code is None:
            # suggest the nearest textually?
            sys.exit(2)

        if self.out_currency:
            self.out_code = self.csc.get_currency_code(self.out_currency)
            if self.out_code is None:
                # suggest the nearest textually?
                sys.exit(2)

    def convert(self):
        # connected to internet?
        # start redis if not running


        prinf('converting in=%s, out=%s', self.in_currency, self.out_currency)
        self.convert_to_ccode()
        prinf('converted in=%s, out=%s', self.in_code, self.out_code)

        if self.in_code == self.out_code:
            self.out_amount = self.in_amount
        else:
            self.sql_to_pandas()
            df = self.rates_df
            df.index = df['index']
            rate = df[self.in_code].loc[self.out_code]
            prinf('rate = %s', rate)

            self.out_amount = round(self.in_amount * rate, self.digits)
        self.print_json()

    def print_json(self):
        self.out_dict = {self.strs[jpn.key_input]: {self.strs[jpn.key_in_amount]: float(self.in_amount),
                                                    self.strs[jpn.key_in_ccode]: self.in_code},
                         self.strs[jpn.key_output]: {self.out_code: float(self.out_amount)}
                         }
        print(self.out_dict)


def parse_arguments():
    epilog = '''Currency codes according to http://www.xe.com/iso4217.php'''
    parser = argparse.ArgumentParser(description='Convert amount of one currency to another.',
                                     epilog=epilog)
    parser.add_argument('--amount', type=float, required=True, help='Money amount to be exchanged')
    parser.add_argument('--input_currency', required=True, help='Input currency code / symbol')
    parser.add_argument('--output_currency', help='Output currency code / symbol')
    args = parser.parse_args()
    amount = args.amount
    input_cur = args.input_currency
    output_cur = args.output_currency

    return amount, input_cur, output_cur

if __name__ == '__main__':
   params = parse_arguments()
   start = time.time()
   cc = CurrencyConverter(*params)
   cc.convert()
   prinf('%s complete code sec', time.time() - start)
