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

#logging.basicConfig(filename='run.log', filemode='w', level=logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)
#logging.basicConfig(level=logging.WARNING
pd.options.display.max_rows = 20

global DEBUG
DEBUG = ''  # 'simulate_time,'
DEBUG = 'simulate_time,'

#TODO
# [] one commit - in master branch - multiple in other branches
# [] another site then fixer
# [] comments
# [] PIP8
# [] readme.md
# [] commit to master


from parameter_names_enums import JsonParameterNames as jpn

from currency_symbol_converter import CurrencySymbolConverter

#from currency_converter_site import CurrencyConverterSite
from currency_converter_site_fixer import CurrencyConverterSiteFixer as CCS_Fixer
from currency_converter_site_apilayer import CurrencyConverterSiteApilayer as CCS_Apilayer

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
        """Calls indiviual initialization methods"""
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
        self.use_sql = True
        self.db_engine_path = 'sqlite:///db\\exchange_rates.db'
        self.db_file = 'db/exchange_rates.db'
        self.rates_table_name = 'rates'
        self.engine = None

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
            #CCS_Apilayer(),
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

        self._start_()
        redis_db = redis.StrictRedis(host="localhost", port=6379, db=0)
        self._end_('redis strictRedis initialized')
        self._start_()
        redis_db.set('redis', 'running')  # takes ~ 1000 ms on windows
        first_contact = self._end_('first redis access')
        self._start_()
        redis_running = redis_db.get('redis') == 'running'  # takes ~ 0.1 ms on windows
        self._end_('second redis access')
        redis_running = redis_db.info()['loading'] == 0

        if first_contact > self.first_contact_max_sec:
            # we don't want the redis to actually slow things down on Windows
            redis_running = False

        if redis_running:
            self._start_()
            self.r = Root(host="localhost", port=6379, db=0)
            self._end_('redisworks root initialized')
            prinf('Redis works root server running.')

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
            self.request_sites_from_net()

            prinf(self.sites)
            with open(self._sites_file_, 'wb') as output:
                pickle.dump(self.sites, output, pickle.HIGHEST_PROTOCOL)
            prinf('%s saved', self._sites_file_)

    def create_rates_table_in_pandas(self, sites=None):
        # take rates data from the most recent site
        site = get_latest_site(sites)

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

        return self.rates_df, self.rates_info_lines

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
            else:
                return None
        else:
            return None

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

    def internet_on(self):
        """Tries to reach google.com to find out if the connection to internet is established

        returns True on conected to internet False otherwise
        """
        try:
            # connect to the google.com -- tells us if the host is actually reachable
            self._start_()
            socket.create_connection(("www.google.com", 80), timeout=1)
            self._end_('connection to internet is available')
            return True
        except OSError:
            pass
        return False

    def get_db_valid_from(self):
        """Returns offline sql database valid_from utc time

        was usefull when the valid_to was stored in multiple sources, it returned the first found entry
        - txt file - now default
        - sql database - obsolete - too slow access
        - redis database - possible in future releases
        """
        db_valid_from = self.get_db_valid_from_via_txt()
        return db_valid_from

    def get_db_valid_from_via_txt(self):
        """Returns offline sql database valid_from utc time from txt file [rates_info_txt_file]"""
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
                    db_valid_from = arrow.get(db_valid_from_str)
                    #db_valid_to = arrow.get(db_valid_to_str)

            self._end_('loaded rates_info_txt_file') # ~ 8 ms
            return db_valid_from
        else:
            prinw('rates_info_txt_file does not exist')
            return None


    def get_utc_now(self):
        """Returns current UTC time

        if global DEBUG variable contains 'simulate_time', the time will be shifted 12 days to the future
        for the offline database update triggering
        """
        global DEBUG
        # simulating different time
        utc_now = arrow.utcnow()
        prinf('%s utc_now', utc_now)
        if 'simulate_time' in DEBUG:
            utc_now = utc_now.shift(days=+12, hours=+4)
            prinf('%s simulated utc_now', utc_now)
        return utc_now


    def sites_update_new_rates_availability(self):
        """Updates [latest_updated] date and [update_needed] for all cc-sites

        - according to [utc_now] and database [valid_from] date
        """
        utc_now = self.get_utc_now()
        utc_db_valid_from = self.get_db_valid_from()
        [site.new_rates_available(utc_db_valid_from, utc_now) for site in self.sites]

    def sites_update_last_updated(self):
        """Updates [latest_updated] date for all cc-sites

        - according to [utc_now]
        """
        utc_now = self.get_utc_now()
        [site.latest_rates_update(utc_now) for site in self.sites]

    def get_latest_site(self, update_needed=False):
        """Finds out which cc-site can give us the most fresh rates

        returns None if none of the cc-sites has more fresh rates data if [update_needed] is True
        """
        if update_needed:
            self.update_new_rates_availability()
            latest_update_times = [site.last_updated for site in self.sites if site.update_needed]
        else:
            self.sites_update_last_updated()
            latest_update_times = [site.last_updated for site in self.sites ]
        if len(latest_update_times) > 0:
            _, idx = max(latest_update_times)
            freshest = self.sites[idx]
            prinf('%s is the most fresh site', freshest.name)
            return freshest
        else:
            return None

    def get_latest_site_than_database(self):
        """Finds out which cc-site can give us the most fresh rates

        returns None if none of the cc-sites has more fresh rates data
        """
        return get_latest_site(update_needed=True)

    def get_latest_site_from_now(self):
        return get_latest_site(update_needed=False)

    def request_sites_from_net(self, sites=None):
        """Gets all successfulness of cc-sites responses (get_all_rates) = True / False

        - counts unsuccessful atempts into [no_response_count]
        -- triggers internet connection detection [internet_on] when past [no_response_trigger]
        - does not store the returns as they are stored in individual cc-sites class instances [site.rates]
        return True on at least one successfull cc-site response, False otherwise
        """
        if sites is None:
            sites = self.sites

        no_response_count = 0
        responded_count = 0
        if type(sites) is list and len(sites) > 1:
            no_response_trigger = self.no_response_trigger
            for site in sites:
                success = site.get_all_rates()
                if not success:
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

    def update_rates_data_from_web(self, site):
        """

        - if more sites are passed as argument [sites]
        -- selects the site with the latest update from them all
        """
        # need to get data from the internet
        responded = self.request_sites_from_net(sites)
        if not responded:
            prinw('Not even one cconversion site responded - possible internet connection problem!')
            return
        else:
            sites = [site for site in sites if site.responded]

        # only the most fresh site continues
        site = self.get_latest_site_than_database(sites)

        self.create_rates_table_in_pandas(site)
        # store them to database
        if self.use_sql:
            self.save_to_sql()
        else:
            prinw('Not using offline sql database!')


    def update_rates_data_if_needed(self):
        """Collect the latest rates from internet if the offline database is outdated

        if database
        - get database valid_from time (db_valid_from)
        - get sites latest_updated times
        - get sites update_needed
        - sort update_needed sites according to last_updated
        - try with the latest site

            -- connect and
            update database
        -- if not try with another !!
        -- if no response - error

        if not database
        -get sites latest_updated times
        - sort update_needed sites according to last_updated
        - try with the latest site

            -- connect and
            update database
        -- if not try with another !!
        -- if no response - error

        - find out if any cconversion site has more fresh data (get_sites_states)
        - gets the most fresh site and update the offline database (update_rates_data_from_web)

        """


        db_valid_from = self.get_db_valid_from()
        if db_valid_from is None:
            # no database rates
            latest_site = self.get_latest_site_from_now()
            self.update_rates_data_from_web()
        else:


            if any(update_needed):
                if len(latest_updates) > 1:
                    # more sites - get the latest update
                    _, idx = max(latest_updates)
                else:
                    idx = 0

                actual_site = self.sites[idx]
                self.update_rates_data_from_web(actual_site)

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

if __name__ == '__main__':
    """Converts amount of currency according to program arguments
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
    cc.update_rates_data_if_needed()
    cc.convert(*params)

    prinf('%s ms - complete code', round((time.time() - start_time)*1000, 2))
    # ~ 44 ms on windows w/o redis

    #print('\n'.join(dir(cc)))
