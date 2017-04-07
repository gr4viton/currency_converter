#!/usr/bin/python
# -*- coding: utf-8 -*-
# task assignment here:
# https://gist.github.com/MichalCab/3c94130adf9ec0c486dfca8d0f01d794

import redis
from redisworks import Root
# import hiredis # would be faster..

import requests
import json
#import BeautifulSoup

import sys

import argparse

import time

import arrow # better then time
from sqlalchemy import create_engine
#from sqlalchemy.orm import sessionmaker

import pandas as pd
pd.options.display.max_rows = 20

import pickle # dev
from pathlib import Path

import logging
#logging.basicConfig(filename='run.log', filemode='w', level=logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)
#logging.basicConfig(level=logging.WARNING)

from logging import info as prinf
from logging import debug as prind
from logging import warning as prinw
from logging import error as prine

global DEBUG
#DEBUG = 'simulate_time'
DEBUG = ''

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

from parameter_names_enums import JsonParameterNames as jpn

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

    def __init__(self, amount, input_cur, output_cur, use_redis):
        #redis port = 6379

        self.sites_file = 'sites.pickle'

        self.in_amount = amount
        self.in_currency = input_cur

        self.out_currency = output_cur
        self.out_amount = None
        self.in_code = None
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
        self.rates_info_table_name = 'rates_info'
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
        self.first_contact_max_sec = 0.08

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

        if redis_running :
            self._start_()
            self.r = Root(host="localhost", port=6379, db=0)
            self._end_('redisworks root initialized')
            prinf('Redis works root server running.')

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
            self.rates_info_df = pd.DataFrame({'source': site.name,
                                               'valid_from_utc': str(site.valid_from_utc),
                                               'valid_to_utc': str(site.valid_to_utc),
                                               'base_ccode': base}, index=[1])

            self.rates_info_lines = '\n'.join([str(site.valid_from_utc), str(site.valid_to_utc)])

    def save_to_sql(self):
        self.create_engine()
        with self.engine.connect() as conn, conn.begin():
            self._start_()
            self.rates_df.to_sql(self.rates_table_name, conn, if_exists='replace')
            self._end_('saved rates_df.to_sql')

            self._start_()
            self.rates_info_df.to_sql(self.rates_info_table_name, conn, if_exists='replace')
            self._end_('saved rates_info_df.to_sql')

            #prinf('Saved to database:\n%s', self.rates_info_df)

            # write to file too
            self._start_()
            with open(self.rates_info_txt_file, 'w', encoding=self.encoding) as f:
                f.writelines(self.rates_info_lines)
            self._end_('saved rates_info_txt_file')

    def _start_(self):
        self._start_time_ = time.time()

    def _end_(self, text=''):
        end_time = time.time() - self._start_time_
        prinf('%s sec %s', end_time, text)
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
                    #sql_query = 'SELECT "index",CZK FROM {} WHERE "index"=CZK;'.format(self.rates_table_name)
                    prinf(sql_query)

                    #sql_query = 'SELECT {} FROM {} WHERE {} = {}'.format(
                     #   '*', self.rates_table_name, 'index', 'CZK')
                    self._start_()
                    in_col_df = pd.read_sql_query(sql_query, self.engine)#, index_col='index')
                    self._end_('loaded query read_sql_query')
                    #prinf(in_col_df)

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
                if len(whole) != 2:
                    prinw('rates_info_txt_file is empty')
                    return None
                else:
                    db_valid_to_str, db_valid_from_str = whole
                    db_valid_to = arrow.get(db_valid_to_str)

            self._end_('loaded rates_info_txt_file') # ~ 8 ms
            return db_valid_to
        else:
            prinw('rates_info_txt_file does not exist')
            return None

    def get_db_valid_to_from_sql(self):
        if not self.db_file_exist():
            # create empty database file
            open(self.db_file, 'a').close()

        if self.db_file_exist():
            self.create_engine()

            self._start_()
            rates_info_table_exist = self.engine.dialect.has_table(self.engine, self.rates_info_table_name)
            self._end_('has_table querry ended') # ~ 4 ms

            if not rates_info_table_exist:
                return None
            else:

                # - find out if we need to request new data
                with self.engine.connect() as conn, conn.begin():
                    self._start_()
                    # find out database valid_to
                    db_rates_info_df = pd.read_sql_table(self.rates_info_table_name, self.engine)
                    self._end_('loaded rates_info_table_sql') # ~ 27 ms
                    prinf('loaded database db_rates_info_df:\n%s', db_rates_info_df)
                    db_valid_to_str = str(db_rates_info_df['valid_to_utc'][0])
                    db_valid_to = arrow.get(db_valid_to_str)

                return db_valid_to


        else:
            prinw("""Offline database file is not present, even after creation attempt."""
                  """\nPlease create empty file in this path: <%s>"""
                  """\nWorking without offline sql database can be slow - for every request there is internet connection needed"""
                  , str(Path(self.db_file)))
            self.use_sql = False
            return None

    def get_db_valid_to(self):
        db_valid_to = self.get_db_valid_to_from_txt()
        if db_valid_to is None:
            db_valid_to = self.get_db_valid_to_from_sql()
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
        prinf('update needed in sites:\n%s\nlatest_update dates:\n%s', update_needed, latest_updates )
        return update_needed, latest_updates

    def update_rates_data_from_web(self, sites=None):
        # need to get data from the internet
        self.request_sites_from_net(sites)
        self.sites_to_pandas(sites)
        # store them to database
        if self.use_sql:
            self.save_to_sql()
        else:
            prinw('Not using offline sql database!')

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

    def convert(self):
        # connected to internet?
        # start redis if not running


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
   start_time = time.time()
   use_redis = False # on windows - 1 sec time penalty on first contact
   cc = CurrencyConverter(*params, use_redis=use_redis)
   cc.convert()
   prinf('%s complete code sec', time.time() - start_time)
   # ~ 44 ms on windows w/o redis
