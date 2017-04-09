from logging import info as prinf
from logging import debug as prind
from logging import warning as prinw
from logging import error as prine


class CurrencySymbolConverter():
    """Manages a conversion of known currency symbols to the 3-letter currency code"""

    def __init__(self, r):
        """Initializes all known currency symbols string"""
        self.r = r

        self.ccode_str = u'Kc:CZK,Kč:CZK,$:USD,\xa5:CNY,\xa3:GBP,\xac:EUR'
        self.currency_symbols = None

    def init_currency_symbols(self):
        """Parses currency symbol string (ccode_str) and generates conversion dictionary [currency_symbols]

        - if the redis is used, the [currency_symbols] is stored in it
          otherwise it uses plain dictionary
        """

        if self.r is not None and self.r.csc.initialized == True:
            self.currency_symbols = self.r.csc.currency_symbols
            self.r.csc.initialized = True
            prinf('currency_symbols loaded from redis')
        else:
            twin_del = ','
            dict_del = ':'
            self.currency_symbols = {
                key: value
                for key,value in [key_value.split(dict_del)
                                  for key_value in self.ccode_str.split(twin_del)]
                }

            prinf('currency_symbols = %s', self.currency_symbols)

            if self.r:
                self.r.csc.currency_symbols = self.currency_symbols
                prinf('currency_symbols saved in redis')
                prinf(self.r.csc.currency_symbols)
                self.r.csc.initialized = True

    def get_currency_code(self, currency_str):
        """Analyses input currency string, converts to ccode if needed"""
        if len(currency_str) == 3:
            if all([char.isupper() for char in currency_str]):
                # the currency_str has 3 chars and its all upper letters
                # - according to http://www.xe.com/symbols.php it is probably currency code
                return currency_str

        if self.currency_symbols is None:
            self.init_currency_symbols()

        dir(self.currency_symbols) # needed for redis_works to work - LazyDot object initialion
        ccode = self.currency_symbols.get(currency_str, None)
        if ccode:
            return ccode
        else:
            prine('Currency symbol [%s] is not in our database.', self.currency_str)
            return None

