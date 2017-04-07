#!/usr/bin/python
# -*- coding: utf-8 -*-
# task assignment here:
# https://gist.github.com/MichalCab/3c94130adf9ec0c486dfca8d0f01d794

import socket  # internet connection detection

import redis
from redisworks import Root
# import hiredis # would be faster..

import requests
import json
#import BeautifulSoup
import platform

import sys
import argparse
import time

import arrow # better then time
from sqlalchemy import create_engine
#from sqlalchemy.orm import sessionmaker


import pickle  # for dev only
from pathlib import Path

import logging

from logging import info as prinf
from logging import debug as prind
from logging import warning as prinw
from logging import error as prine

import pandas as pd
pd.options.display.max_rows = 20

#logging.basicConfig(filename='run.log', filemode='w', level=logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)
#logging.basicConfig(level=logging.WARNING
global DEBUG
DEBUG = ''
#DEBUG = 'simulate_time'

#TODO
# [] one commit - in master branch - multiple in other branches
# [] another site then fixer
# [] comments
# [] PIP8
# [] readme.md
# [] commit to master


### OUTPUT
# - json with following structure:
#```
# {
#    "input": {
#         "amount": <float>,
#         "currency": <3 letter currency code>
#     }
#     "output": {
#         <3 letter currency code>: <float>
#     }
# }
# ```



### Featuring
# - smart internet connection and currency conversion sites response detection
# -- currency conversion sites implemented: fixer.io
# - offline currencies database
# -- automatic offline database update on detection of new rates update from any implemented site
# --- data_valid_utc is stored separately in txt file - faster then another sql database query
# - time effective conversion
# -- tested on windows 64
# --- w/o update offline database triggered : ~ 50 ms
# --- else : ~ 1200ms
# - standard logger for logging
# - argparser for input argument parsing - help string autogeneration
# - manually tested
# -- 3 types input arguments from assignment <https://gist.github.com/MichalCab/3c94130adf9ec0c486dfca8d0f01d794>
# -- another common currency symbols - Kč, $, CNY-symbol, GBP-symbol, EUR-symbol
# - used modules:
# -- pandas, sqlalchemy, redis, redisworks, requests, json
# -- arrow, argparse
# -- platform, socket, sys, time, pathlib, logging, pickle
# - using decorators: staticmethod, classmethod



### Disclaimer
#### Not using these controversial tricks to get lower latency
##### [x] Immediate exchange rate json output after reading (from sql/redis)
#  - implemented style: First the program tries to find out if the database should be updated
#  - not implemented: First run the program returns json data from offline database
#   -- even if in second thread updating the database afterwards
#   -- user gets better response time, but the first time he calls, he can get outdated rates
#    --- we certainly don't want that on the first start after a long time (olddated sql database)
#    --- it can be implemented w/o further ado, but only if the server with redis is updated frequently

#### Not implemented (yet) - future releases maybe
# - full redis support for rates
# -- expire time - to the known time of next update from any implemented site
# - currency conversion rates from multiple sources in the offline database
# -- e.g. if CZK is not in the selected most fresh currency converter site - it will not be converted to/from
# - multithreading - load from database at start in different thread - use the data or not later
# -- after finding the offline data are not fresh enough
# - automatic database update as a background service
# -- would update sql database and redis automatically not needed to check every time the convert is triggered
# - automatic testing via asserts and node2 module
# - user input error autocorrection
# -- suggestion of the textually nearest currency
# -- another program argument for automatic nearest suggestion conversion
# -- localisation of output / logger texts into other languages
# - modules to possibly use:
# -- hiredis - can be 10 times faster on windows..
# -- BeautifulSoup - for automatic currency symbol to currency code conversion from site <http://www.xe.com/symbols.php>

from parameter_names_enums import JsonParameterNames as jpn

from currency_converter_site import CurrencyConverterSite
from currency_converter_site_fixer import CurrencyConverterSiteFixer
from currency_symbol_converter import CurrencySymbolConverter
#class CurrencyConverterSiteApilayer(CurrencyConverterSite):





class CurrencyConverter():

    strs = {jpn.key_input: 'input',
            jpn.key_in_amount: 'amount',
            jpn.key_in_ccode: 'currency',
            jpn.key_output: 'output'}

    def __init__(self, use_redis):

        self.sites_file = 'sites.pickle'

        self.in_amount = None
        self.in_currency = None
        self.in_code = None

        self.out_currency = None
        self.out_amount = None
        self.out_code = None
        self.out_digits = 2

        self.init_sql()
        self.init_txt()

        self.init_redis(use_redis)

        self.init_csc()

        self.init_cc_sites()
        self.update_rates_data()

    def init_sql(self):
        self.use_sql = True
        self.db_engine_path = 'sqlite:///db\\exchange_rates.db'
        self.db_file = 'db/exchange_rates.db'
        self.rates_table_name = 'rates'
        self.engine = None

    def init_txt(self):
        self.rates_info_txt_file = 'db/rates_info.nfo'
        self.encoding = 'utf-8'

    def init_csc(self):
        self.csc = CurrencySymbolConverter(self.r)

    def init_redis(self, use_redis):
        self.use_redis = use_redis
        # WINDOWS NOTE
        # the first access to redis has about 1 second time penalty on windows platform. idiocracy
        self.first_contact_max_sec = 20.5

        self.redis_host = 'localhost'
        self.redis_port = 6379

        self.r = None

        if not self.use_redis:
            return

        self._start_()
        redis_db = redis.StrictRedis(host="localhost", port=6379, db=0)
        self._end_('redis strictRedis initialized')

        self._start_()
        redis_db.set('redis', 'running')
        first_contact = self._end_('first redis access') # ~ 1000 ms on windows

        self._start_()
        redis_running = redis_db.get('redis') == 'running'
        self._end_('second redis access') # ~ 0 ms on windows

        redis_running = redis_db.info()['loading'] == 0

        if first_contact > self.first_contact_max_sec:
            # we don't want the redis to actually slow things down
            redis_running = False

        if redis_running:
            self._start_()
            self.r = Root(host="localhost", port=6379, db=0)
            self._end_('redisworks root initialized')
            prinf('Redis works root server running.')

    def init_cc_sites(self):
        self.sites = []
        self.init_curconv_site_fixer()

        # when using more cconverter sites - it can happen that some of them do not respond
        # if more then <no_response_trigger> sites do not respond - it will trigger internet_on() detection
        self.no_response_trigger = 3

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

        no_response_count = 0
        responded_count = 0
        if len(sites) > 1:
            no_response_trigger = self.no_response_trigger
            for site in sites:
                response = site.get_all_rates()
                if not response:
                    no_response_count += 1
                else:
                    responded_count += 1
                if responded_count == 0 and no_response_count > no_response_trigger :
                    # when at least <no_response_trigger> count sites don't respond
                    # - trigger internet connection detection
                    if not self.internet_on():
                        return False
                    else:
                        # if the internet is connected - add up <no_response_trigger>
                        no_response_trigger += self.no_response_trigger
        else:
            # not useful to try connection to internet (~60ms)
            # if only one cconvertion site is available
            if sites[0].get_all_rates():
                responded_count = 1

        at_least_one_site_responded = responded_count > 0
        return at_least_one_site_responded

    def _load_sites_from_pickle_(self):
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

            df = pd.DataFrame({base : rates})
            #df[base] = rates
            df.index = ccodes

            # calculate other values from base column - do not round digits
            for col_ccode in ccodes:
                if col_ccode != base:
                    col = [df[base].loc[row_ccode] / df[base].loc[col_ccode] for row_ccode in ccodes]
                    col = [round(df[base].loc[row_ccode] / df[base].loc[col_ccode], 4) for row_ccode in ccodes]
                    df[col_ccode] = col

            self.rates_df = df

            self.rates_info_lines = '\n'.join([str(i) for i in [site.valid_from_utc, site.valid_to_utc,
                                                                site.name, base]])

    def save_to_sql(self):
        self.create_engine()
        self.touch_db_file()
        with self.engine.connect() as conn, conn.begin():
            self._start_()
            self.rates_df.to_sql(self.rates_table_name, conn, if_exists='replace')
            self._end_('saved rates_df.to_sql')

            # write to file too
            self._start_()
            with open(self.rates_info_txt_file, 'w', encoding=self.encoding) as f:
                f.writelines(self.rates_info_lines)
            self._end_('saved rates_info_txt_file')

    def _start_(self):
        self._start_time_ = time.time()

    def _end_(self, text=''):
        end_time = time.time() - self._start_time_
        prinf('%s ms %s', round(end_time*1000,2), text)
        return end_time

    def create_engine(self):
        self._start_()
        if self.engine is None:
            self.engine = create_engine(self.db_engine_path)
        self._end_('created engine')

    def db_file_exist(self):
        return Path(self.db_file).is_file()

    def sql_to_pandas(self, in_ccode=None, out_ccode=None):
        if self.db_file_exist():
            self.create_engine()

            rates_table_exist = self.engine.dialect.has_table(self.engine, self.rates_table_name)
            if rates_table_exist:

                if not (in_ccode or out_ccode):
                    self._start_()
                    # load whole database to pandas (time consuming)
                    rates_df = pd.read_sql_table(self.rates_table_name, self.engine)
                    self._end_('loaded database')

                    rates_df.index = rates_df['index']
                    rate = rates_df[self.in_code].loc[self.out_code]

                    return rate

                elif in_ccode:
                    sql_query = 'SELECT "index", {} FROM {} ;'.format(in_ccode, self.rates_table_name)
                    self._start_()
                    in_col_df = pd.read_sql_query(sql_query, self.engine)
                    self._end_('loaded query read_sql_query')

                    if out_ccode:
                        in_col_df.index = in_col_df['index']
                        rate = in_col_df[in_ccode].loc[out_ccode]

                        return rate
                    else:
                        rates = {ccode: float(rate) for ccode, rate
                                                    in zip(in_col_df['index'], in_col_df[in_ccode])}
                        return rates


    def get_db_valid_to_from_txt(self):
        # database rates exist - so rates_info_txt should exist too
        # not use database for loading rates_info_table_exist = use file - faster access
        rates_info_txt_exist = Path(self.rates_info_txt_file).is_file()
        if rates_info_txt_exist:
            self._start_()
            with open(self.rates_info_txt_file, 'r', encoding=self.encoding) as f:
                whole = f.readlines()
                if len(whole) < 2:
                    prinw('rates_info_txt_file does not contain lines with db_valid_to_str, db_valid_from_str!')
                    return None
                else:
                    db_valid_to_str, db_valid_from_str = whole[0:2]
                    db_valid_to = arrow.get(db_valid_to_str)

            self._end_('loaded rates_info_txt_file') # ~ 8 ms
            return db_valid_to
        else:
            prinw('rates_info_txt_file does not exist')
            return None

    def touch_db_file(self):
        if not self.db_file_exist():
            # create empty database file
            open(self.db_file, 'a').close()

        if not self.db_file_exist():
            prinw("""Offline database file is not present, even after creation attempt."""
                  """\nPlease create empty file in this path: <%s>"""
                  """\nWorking without offline sql database can be slow - for every request there is internet connection needed"""
                  , str(Path(self.db_file)))
            self.use_sql = False
            return None

    def get_db_valid_to(self):
        db_valid_to = self.get_db_valid_to_from_txt()
        return db_valid_to


    def get_utc_now(self):
        global DEBUG
        # simulating different time
        utc_now = arrow.utcnow()
        prinf('%s utc_now', utc_now)
        if 'simulate_time' in DEBUG:
            utc_now = utc_now.shift(days=+12, hours=+4)
            prinf('%s simulated utc_now', utc_now)
        return utc_now

    def get_sites_states(self, db_valid_to):
        utc_now = self.get_utc_now()
        # which sites can give us later rates then the ones saved in database
        update_need_and_time = [
            site.__class__.new_rates_available(utc_db_valid_to=db_valid_to,
                                               utc_now=utc_now)
                                               for site in self.sites]
        update_needed, latest_updates = zip(*update_need_and_time)
        prinf('update needed in sites:\n%s\nlatest_update dates:\n%s', update_needed, latest_updates)
        return update_needed, latest_updates

    def update_rates_data_from_web(self, sites=None):
        # need to get data from the internet
        responded = self.request_sites_from_net(sites)
        if not responded:
            prinw('Not even one cconversion site responded - possible internet connection problem!')
            return

        # only the most fresh site continues
        if type(sites) == list and len(sites) > 1:
            sites_valid_from = {site: site.valid_from_utc for site in sites
                                if site.responded is not None}
            latest_valid_from_utc = max(sites_valid_from.values())
            latest_site = [site for site, valid_from_utc
                           in sites_valid_from
                           if valid_from_utc == latest_valid_from_utc]
            sites = latest_site
            prinf('%s is the most fresh site', latest_site.name)

        self.sites_to_pandas(sites)
        # store them to database
        if self.use_sql:
            self.save_to_sql()
        else:
            prinw('Not using offline sql database!')

    def internet_on(self):
        try:
            # connect to the host -- tells us if the host is actually reachable
            self._start_()
            socket.create_connection(("www.google.com", 80), timeout=1)
            self._end_('connection to internet is available')
            return True
        except OSError:
            pass
        return False

    def update_rates_data(self):
        db_valid_to = self.get_db_valid_to()
        if db_valid_to is None:
            self.update_rates_data_from_web()
        else:
            update_needed, latest_updates = self.get_sites_states(db_valid_to)

            if any(update_needed):
                if len(latest_updates) > 1:
                    # more sites - get the latest update
                    _, idx = max(latest_updates)
                    prinf(idx)
                else:
                    idx = 0

                actual_site = self.sites[idx]
                self.update_rates_data_from_web(actual_site)

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

    def convert(self, amount, input_cur, output_cur=None):
        """ Converts amount of money in <input_cur> currency to <output_cur> currency
        amount <float> - Money amount to be converted
        input
        """
        self.in_amount = amount
        self.in_currency = input_cur
        self.out_currency = output_cur
        if not all([self.in_amount, self.in_currency]):
            prine('Arguments [amount] and [input_cur] are both required to convert!')
            return None

        prinf('converting in=%s, out=%s', self.in_currency, self.out_currency)
        self.convert_to_ccode()
        prinf('converted in=%s, out=%s', self.in_code, self.out_code)

        if self.in_code == self.out_code:
            self.out_amount = self.in_amount
        else:
            rates = self.sql_to_pandas(self.in_code, self.out_code)

            prinf('rate = %s', rates)
            if type(rates) is not dict:
                self.out_amount = round(self.in_amount * rates, self.out_digits)
                self.print_json()
            else:
                self.out_amount = None
                rates = {key: round(self.in_amount * value, self.out_digits) for key, value in rates.items()}
                self.print_json(rates_dict=rates)

    def print_json(self, rates_dict=None):
        if not rates_dict:
            rates_dict = {self.out_code: float(self.out_amount)}
        self.out_dict = {self.strs[jpn.key_input]: {self.strs[jpn.key_in_amount]: float(self.in_amount),
                                                    self.strs[jpn.key_in_ccode]: self.in_code},
                         self.strs[jpn.key_output]: rates_dict
                         }
        self.json_out = json.dumps(self.out_dict, indent=4, sort_keys=True)
        print(self.json_out)


def parse_arguments():
    """ Parses program arguments
    --amount - amount which we want to convert - float
    --input_currency - input currency - 3 letters name or currency symbol
    --output_currency - requested/output currency - 3 letters name or currency symbol
    """
    epilog = '''Currency codes according to http://www.xe.com/iso4217.php'''
    parser = argparse.ArgumentParser(description='Convert amount of one currency to another.',
                                     epilog=epilog)
    parser.add_argument('--amount', type=float, required=True,
                        help='Amount which we want to convert - float')
    parser.add_argument('--input_currency', required=True,
                        help='Input currency - 3 letters name or currency symbol')
    parser.add_argument('--output_currency',
                        help='Requested/output currency - 3 letters name or currency symbol')
    args = parser.parse_args()
    amount = args.amount
    input_cur = args.input_currency
    output_cur = args.output_currency

    return amount, input_cur, output_cur

if __name__ == '__main__':
    """ Converts amount of currency according to program arguments
    - Program arguments parsing
    - Redis usage decision
    - CurrencyConverter initializaton
    - Conversion according to parsed arguments
    """
    start_time = time.time()

    # parsing of arguments
    params = parse_arguments()

    # redis usage
    use_redis = True
    use_redis_on_windows = False
    if platform.system() == 'Windows':
        # on windows - 1 sec time penalty on first contact with redis
        use_redis = use_redis_on_windows
        prinw('Not using redis - Windows platform has 1 sec latency on first contact!')

    # main code
    cc = CurrencyConverter(use_redis=use_redis)
    cc.convert(*params)

    prinf('%s ms - complete code', round((time.time() - start_time)*1000, 2))
    # ~ 44 ms on windows w/o redis

    #print('\n'.join(dir(cc)))
