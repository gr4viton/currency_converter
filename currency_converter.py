#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Project:    Currency converter
Assignment: https://gist.github.com/MichalCab/3c94130adf9ec0c486dfca8d0f01d794
Author:     Daniel Davídek @ gr4viton.cz
Originated: 03-04-2017
License:    GPLv3 @ http://www.gnu.org/licenses/gpl-3.0.html

Disclaimer: I apologize for the "long" code.
            I tried to create it universally with modularity in mind
            I use retrospective as an antonym to chronological, even it is not a correct global meaning.
"""

import requests
import json
import pandas as pd
from sqlalchemy import create_engine
import redis
from redisworks import Root

import argparse  # better than getopt
import arrow  # better than time
import pickle  # for dev only (_load_sites_from_pickle_)

import sys
import time  # time interval measurement
import platform  # windows detection
import socket  # internet connection detection
from pathlib import Path  # file creation detection
import logging

from logging import info as prinf
from logging import debug as prind
from logging import warning as prinw
from logging import error as prine

from parameter_names_enums import JsonParameterNames as jpn
from currency_symbol_converter import CurrencySymbolConverter
from currency_converter_site_fixer import CurrencyConverterSiteFixer as CCS_Fixer
from currency_converter_site_currencylayer import CurrencyConverterSiteCurrencylayer as CCS_Currencylayer

from global_timer import g_start, g_end

logging.basicConfig(level=logging.DEBUG)
# logging.basicConfig(level=logging.WARNING)
pd.options.display.max_rows = 20

global DEBUG  # DEBUG = 'simulate_time,'
DEBUG = ''


class CurrencyConverter():
    """Takes care of all the currency conversion bussiness:

    - currency conversion sites communication (through implemented classes)
    - currency symbols to 3 letter currency codes conversion
    - sql and redis rates database update and creation
    """
    strs = {jpn.key_input: 'input',
            jpn.key_in_amount: 'amount',
            jpn.key_in_ccode: 'currency',
            jpn.key_output: 'output'}

    def __init__(self, use_redis, ccs_sites_list=[]):
        """Calls individual initialization methods"""
        self._sites_file_ = 'sites.pickle'  # for development only
        self.in_amount = None
        self.in_currency = None
        self.in_code = None

        self.out_currency = None
        self.out_amount = None
        self.out_code = None
        self.out_digits = 2  # assignment specific choice

        self._init_sql_()
        self._init_txt_()
        self._init_redis_(use_redis)
        self._init_csc_()
        self._init_cc_sites_(ccs_sites_list)

    def _init_sql_(self):
        """Initialize offline sql disk database variables"""
        self._valid_database_exists = None
        self.db_valid_from = None
        self.use_sql = True
        self.db_engine_path = 'sqlite:///db\\exchange_rates.db'
        self.db_file = 'db/exchange_rates.db'
        self.rates_table_name = 'rates'
        self.engine = None
        self.database_digits = 4

    def _init_txt_(self):
        """Initialize txt file for database valid_to date storing"""
        self.rates_info_txt_file = 'db/rates_info.nfo'
        self.encoding = 'utf-8'

    def _init_csc_(self):
        """Initialize currency symbol converter with redis variable"""
        self.csc = CurrencySymbolConverter(self.r)

    def _init_cc_sites_(self, ccs_sites_list):
        """Initialize currency conversion sites"""
        self.sites = [
            CCS_Fixer(),
            #CCS_Currencylayer(),
        ]
        self.sites.extend(ccs_sites_list)
        # when using more cconverter sites - it can happen that some of them do not respond
        # if more then <no_response_trigger> sites do not respond - it will trigger internet_on() detection
        self.no_response_trigger = 3

    def _init_redis_(self, use_redis):
        """Initialize redis variables and connections

        - even if use_redis is True, the first_contact_max_sec test is still used
        ::WINDOWS NOTE::
        the first access to redis has about 1 second time penalty on windows platform. idiocracy
        """
        self.use_redis = use_redis
        self.first_contact_max_sec = 2.5  # should be at most 300 ms to be better than hdd sql database
        self.redis_host = 'localhost'
        self.redis_port = 6379
        self.r = None
        if not self.use_redis:
            return

        g_start()
        redis_db = redis.StrictRedis(host="localhost", port=6379, db=0)
        g_end('redis strictRedis initialized')
        g_start()
        redis_db.set('redis', 'running')  # takes ~ 1000 ms on windows
        first_contact = g_end('first redis access')
        g_start()
        redis_running = redis_db.get('redis') == 'running'  # takes ~ 0.1 ms on windows
        g_end('second redis access', 'd')
        redis_running = redis_db.info()['loading'] == 0

        if first_contact > self.first_contact_max_sec:
            # we don't want the redis to actually slow things down on Windows
            redis_running = False

        if redis_running:
            g_start()
            self.r = Root(host="localhost", port=6379, db=0)
            g_end('redisworks root initialized')
            prinf('Redis works root server running.')

    @property
    def valid_database_exists(self):
        """Returns True if valid sql database exists

        on first getting it runs a test for database existance (refresh_db_valid_from)
        """
        if self._valid_database_exists is None:
            self.refresh_db_valid_from()
        return self._valid_database_exists

    @staticmethod
    def internet_on():
        """Tries to reach google.com to find out if the connection to internet is established

        returns True on conected to internet False otherwise
        """
        try:
            # connect to the google.com -- tells us if the host is actually reachable
            g_start()
            socket.create_connection(("www.google.com", 80), timeout=1)
            g_end('connection to internet is available')
            return True
        except OSError:
            pass
        return False

    @staticmethod
    def get_utc_now():
        """Returns current UTC time

        if global DEBUG variable contains 'simulate_time', the time will be shifted 12 days to the future
        for the offline database update triggering
        """
        global DEBUG
        utc_now = arrow.utcnow()
        prinf('%s utc_now', utc_now)
        if 'simulate_time' in DEBUG:  # simulating different time
            utc_now = utc_now.shift(days=+12, hours=+4)
            prinf('%s simulated utc_now', utc_now)
        return utc_now

    def _load_sites_from_pickle_(self):
        """Loads exchange rates pandas DataFrame from local pickle

        if it does not exist - get the data from
        """
        if Path(self._sites_file_).is_file():
            with open(self._sites_file_, 'rb') as input:
                self.sites = pickle.load(input)
            prinf('%s loaded', self._sites_file_)
            prinf(self.sites)
        else:
            self.request_site_from_internet()

            prinf(self.sites)
            with open(self._sites_file_, 'wb') as output:
                pickle.dump(self.sites, output, pickle.HIGHEST_PROTOCOL)
            prinf('%s saved', self._sites_file_)

    def create_rates_table_in_pandas(self, site):
        """Extrapolates data exchange rates from the site to create rates between each currency

        - takes all the rates from the sites relative to the base input currency code
        - extrapolates individual rates between every currency and saves them into DataFrame
        - rounds the stored exchange rates to [self.database_digits] decimal places
        """
        base = site.in_ccode
        ccodes_rates = [(key, site.rates[key]) for key in sorted(site.rates.keys())]
        ccodes, rates = zip(*ccodes_rates)

        df = pd.DataFrame({base : rates})
        df.index = ccodes

        # calculate other values from base column - do not round digits
        r = self.database_digits
        for col_ccode in ccodes:
            if col_ccode != base:
                #col = [df[base].loc[row_ccode] / df[base].loc[col_ccode] for row_ccode in ccodes]
                col = [round(df[base].loc[row_ccode] / df[base].loc[col_ccode], r) for row_ccode in ccodes]
                df[col_ccode] = col

        rates_df = df
        rates_info_lines = '\n'.join([str(i) for i in
                                      [site.valid_from_utc, site.valid_to_utc, site.name, base]])

        return rates_df, rates_info_lines

    def save_to_sql(self, rates_df, rates_info_lines):
        """Saves rates database into sql file and database info file to disk"""
        self.create_engine()
        self.touch_db_file()
        with self.engine.connect() as conn, conn.begin():
            # rates sql database
            g_start()
            rates_df.to_sql(self.rates_table_name, conn, if_exists='replace')
            g_end('saved rates_df.to_sql')

            # database info file
            g_start()
            with open(self.rates_info_txt_file, 'w', encoding=self.encoding) as f:
                f.writelines(rates_info_lines)
            g_end('saved rates_info_txt_file')

    def create_engine(self):
        """Creates engine for sql database manipulation, if one does not exist yet"""
        g_start()
        if self.engine is None:
            self.engine = create_engine(self.db_engine_path)
        g_end('created engine')

    def db_file_exist(self):
        """Returns True when database file exists, False otherwise"""
        return Path(self.db_file).is_file()

    def touch_db_file(self):
        """Tries to create empty database file at the desired location

        if unsuccessfully it disables sql database usage
        - the exchange rates from cc-sites will not be stored
        """
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

    def get_rates_from_sql(self, in_ccode=None, out_ccode=None):
        """Queries the sql database for input rates according to input arguments [in_ccode, out_ccode]

        - on no rates table or no sql database it returns None
        - when both arguments are None, returns the full database
        - when out_ccode is None, returns the [in_ccode] rates column
        - otherwise returns the exchange rate for the arguments
        """
        if self.db_file_exist():
            self.create_engine()
            rates_table_exist = self.engine.dialect.has_table(self.engine, self.rates_table_name)
            if rates_table_exist:
                if not (in_ccode or out_ccode):
                    g_start()
                    # load whole database to pandas (time consuming)
                    rates_df = pd.read_sql_table(self.rates_table_name, self.engine)
                    g_end('loaded database')

                    rates_df.index = rates_df['index']
                    rate = rates_df[self.in_code].loc[self.out_code]
                    return rate

                elif in_ccode:
                    sql_query = 'SELECT "index", {} FROM {} ;'.format(in_ccode, self.rates_table_name)
                    g_start()
                    in_col_df = pd.read_sql_query(sql_query, self.engine)
                    g_end('loaded query read_sql_query')
                    if out_ccode:
                        in_col_df.index = in_col_df['index']
                        rate = in_col_df[in_ccode].loc[out_ccode]
                        return rate
                    else:
                        rates = {ccode: float(rate) for ccode, rate
                                                    in zip(in_col_df['index'], in_col_df[in_ccode])}
                        return rates
            else:
                return None
        else:
            return None

    def refresh_db_valid_from(self):
        """Updates offline sql database valid_from utc time

        was usefull when the valid_to was stored in multiple sources, it returned the first found entry
        - txt file - now default
        - sql database - obsolete - too slow access
        - redis database - possible in future releases
        """
        self.db_valid_from = self.get_db_valid_from_via_txt()
        self._valid_database_exists = self.db_valid_from is not None

    def get_db_valid_from_via_txt(self):
        """Returns offline sql database valid_from utc time from txt file [rates_info_txt_file]"""
        rates_info_txt_exist = Path(self.rates_info_txt_file).is_file()
        if rates_info_txt_exist:
            g_start()
            with open(self.rates_info_txt_file, 'r', encoding=self.encoding) as f:
                whole = f.readlines()
                if len(whole) < 2:
                    prinw('rates_info_txt_file does not contain lines with db_valid_to_str, db_valid_from_str!')
                    return None
                else:
                    db_valid_to_str, db_valid_from_str = whole[0:2]
                    db_valid_from = arrow.get(db_valid_from_str)

            g_end('loaded rates_info_txt_file') # ~ 8 ms
            return db_valid_from
        else:
            prinw('rates_info_txt_file does not exist')
            return None

    def update_database_from_site(self, site):
        """Requires exchange rates data from the site and processes them

        - requires all rates data from the currency conversion site
        - creates pandas representation of all the exchange rates
        - saves them to the sql database

        returns - tuple of:
            [update_success] = True on successful data processing, False otherwise
            [response_success] = True when successfully received data, False otherwise
        """
        response_success = site.get_all_rates()
        if not response_success:
            return False, response_success

        rates_df, rates_info_lines = self.create_rates_table_in_pandas(site)
        update_success = True
        if self.use_sql:
            self.save_to_sql(rates_df, rates_info_lines)
        else:
            prinw('Not using offline sql database!')

        return update_success, response_success

    def try_update_database_from_sites(self, sorted_sites):
        """Tries to updates offline database from the freshest site, if not successful continues with another

        - counts unsuccessful attempts into [no_response_count]
        -- triggers internet connection detection [internet_on] when past [no_response_trigger]
        - does not store the returns as they are stored in individual cc-sites class instances [site.rates]

        returns - True on at least one successful cc-site response, False otherwise
        """
        no_response_trigger = self.no_response_trigger
        responded = not_responded = 0
        for site in sorted_sites:
            update_success, response_success = self.update_database_from_site(site)
            if not update_success:
                if response_success:
                    responded += 1
                else:
                    not_responded += 1

                if responded_count == 0 and no_response_count > no_response_trigger :
                    # when at least <no_response_trigger> count sites don't respond
                    # - trigger internet connection detection
                    if not self.internet_on():
                        return False
                    else:
                        # if the internet is connected - add up <no_response_trigger>
                        no_response_trigger += self.no_response_trigger
            else:
                break
        return update_success

    def get_retrospectively_sorted_sites(self, only_sites_fresher_than_db=False):
        """Returns list sites which are ordered retrospectively from the site with freshest data update

        - updates all sites [last_updated] utc time according to their update schedule (refresh_last_updated)
        - filters out sites not fresher then the database if initiated (only_sites_fresher_than_db = True)
        - sort according to reversed chronological order (~ retrospective)

        returns - sorted list of sites
        """
        utc_now = self.get_utc_now()
        [site.refresh_last_updated(utc_now) for site in self.sites]

        # if only_sites_fresher_than_db - get only sites which have data fresher then database
        sites = [site for site in self.sites
                 if site.fresher_than_db(self.db_valid_from) or not only_sites_fresher_than_db
                 ]
        sorted_sites = sorted(sites, key=lambda site: site.last_updated, reverse=True)
        return sorted_sites

    def update_rates_data_if_needed(self):
        """Main decision tree for rates database update from internet"""

        if self.valid_database_exists:
            # we need only new data (fresher then database)
            only_sites_fresher_than_db = True
        else:
            # no database - just try to get data
            only_sites_fresher_than_db = False

        # get sites ordered retrospectively from the one with freshest last_updated utc time
        sorted_sites = self.get_retrospectively_sorted_sites(only_sites_fresher_than_db)

        # try to update offline database starting with the freshest
        any_success = self.try_update_database_from_sites(sorted_sites)
        if not any_success:
            prinw('Conversion rates data were not available in any cconversion site!')

    def convert_to_ccode(self):
        """Converts in_code and out_code to ccode

        ccode = 3 letter currency code
        if the conversion fails the program is ended with
        """
        self.in_code = self.csc.get_currency_code(self.in_currency)
        if self.in_code is None:
            # suggest the nearest textually?
            sys.exit(2)

        if self.out_currency:
            self.out_code = self.csc.get_currency_code(self.out_currency)
            if self.out_code is None:
                # suggest the nearest textually?
                sys.exit(3)

    def convert(self, amount, input_cur, output_cur=None):
        """Converts amount of money in <input_cur> currency to <output_cur> currency

        amount <float> - Amount which we want to convert
        input_cur <str> - Input currency - 3 letters name or currency symbol
        [output_cur <str>] - Output currency - 3 letters name or currency symbol
                           - if omitted - amount converted to all availible currencies
        exchange rates are acquired from sql database (get_rates_from_sql)
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
            rates = self.get_rates_from_sql(self.in_code, self.out_code)

            prinf('rate = %s', rates)
            if type(rates) is not dict:
                self.out_amount = round(self.in_amount * rates, self.out_digits)
                self.print_json()
            else:
                self.out_amount = None
                rates = {key: round(self.in_amount * value, self.out_digits) for key, value in rates.items()}
                self.print_json(rates_dict=rates)

    def print_json(self, rates_dict=None):
        """Sends json formatted conversion output in assignment format manner"""
        if not rates_dict:
            rates_dict = {self.out_code: float(self.out_amount)}
        self.out_dict = {self.strs[jpn.key_input]: {self.strs[jpn.key_in_amount]: float(self.in_amount),
                                                    self.strs[jpn.key_in_ccode]: self.in_code},
                         self.strs[jpn.key_output]: rates_dict
                         }
        self.json_out = json.dumps(self.out_dict, indent=4, sort_keys=True)
        print(self.json_out)


def parse_arguments():
    """Parses program arguments

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


def setup_redis(use_redis=True, use_redis_on_windows=False):
    """The platform detection and redis usage decision tree is hereby created

    as on tested Windows 7 64bit (MSOpenTech 3.2.100) there was one second time penalty
    on first contact with redis
    """
    truly_use_redis = use_redis
    if platform.system() == 'Windows':
        truly_use_redis = use_redis_on_windows
        prinw('Not using redis - Windows platform has 1 sec latency on first contact!')
    return truly_use_redis

if __name__ == '__main__':
    """Converts amount of currency according to program arguments
    - Program arguments parsing
    - Redis usage decision
    - CurrencyConverter initializaton
    - Conversion according to parsed arguments
    """
    g_start('complete code')

    # parsing of arguments
    params = parse_arguments()

    # redis usage
    use_redis = setup_redis(use_redis=True, use_redis_on_windows=False)

    # main code
    cc = CurrencyConverter(use_redis=use_redis)
    cc.update_rates_data_if_needed()
    cc.convert(*params)

    g_end('complete program run', 'complete code')
    # ~ 44 ms on windows w/o redis
