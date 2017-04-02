#!/usr/bin/python
# task assignment here:
# https://gist.github.com/MichalCab/3c94130adf9ec0c486dfca8d0f01d794


import redis

import requests
import json
#import BeautifulSoup
import sys
import getopt



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

class CurrencyConverterSite():
    def __init__(self, name, base, strs):
        self.name = name
        self.base = base
        self.strs = strs

    def get_rates_for(self, in_ccode, my_params={}):
        base_url = self.base

        def _add_path_(try_jpn):
            part = self.strs.get(try_jpn, None)
            if part:
                base_url += part
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

        if _add_param_(jpn.var_date)

        # get server output
        print(base_url, my_params)
        response = requests.get(base_url, params=my_params)

        if not response:
            print(response)
            return None
        results = response.json()[self.strs[jpn.key_output]]
        self.output = [in_ccode, results]
        return self.output


    def get_some_rates_for(self, in_ccode, out_ccode_str, my_params={}):
        my_params.update({self.strs[jpn.var_out_ccode] : out_ccode_str})
        return self.get_rates_for(in_ccode, my_params=my_params)



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

        self.in_amount = amount
        self.in_currency = input_cur
        self.out_currency = output_cur
        self.in_code = self.out_code = None



        fixer_strs = {
            jpn.key_output: 'rate',
            jpn.key_in_ccode: 'base',
            jpn.var_in_ccode: 'base',
            jpn.var_out_ccode: 'symbols',
            jpn.path_latest: 'latest',
        }

        # The rates are updated daily around 4PM CET.
        fixer = CurrencyConverterSite('fixer',
                                      base='http://api.fixer.io/',
                                      strs=fixer_strs
                                      )

        apilayer_strs = {
            jpn.var_in_ccode: 'from',
            jpn.var_out_ccode: 'to',
            jpn.path_latest: 'historical',
            jpn.var_date: 'date',
            jpn.var_date_format: 'YYYY-MM-DD',
            jpn.var_apikey: 'access_key',
            jpn.free_apikey: 'f97e97072345994b708fb559a09788a5',
        }
        apilayer = CurrencyConverterSite('apilayer',
                                          base='http://www.apilayer.net/api',
                                          strs=apilayer_strs )

        site_list = [fixer, apilayer]
        self.sites = {ccs.name : ccs for ccs in site_list}

        in_ccode = 'CZK'
        out_ccode_str = 'EUR,USD'
        #print([ (name, site.get_rates_for(in_ccode)) for name, site in self.sites.items()])
        print([ (name, site.get_some_rates_for(in_ccode, out_ccode_str)) for name, site in self.sites.items()])


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
   cc.convert()