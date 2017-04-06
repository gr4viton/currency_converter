from parameter_names_enums import RedisParameterNames as rpn

class CurrencySymbolConverter():
    def __init__(self, r):
        self.r = r
        self.ccode_str = u'Kc:CZK,Kč:CZK,$:USD,\xa5:JPY,\xa3:GBP,\xac:EUR'
        self.currency_symbols = None
        self.strs = {rpn.csc_initialized: 'currency_symbol_converter_initialized'}

    def init_currency_symbols(self):
        # not needed every time
        if self.r.get(self.strs[rpn.csc_initialized]):
            self.r.get()
            #self.r.set(self.strs[rpn.csc_initialized])

        twin_del = ','
        dict_del = ':'
        self.currency_symbols = {key: value
                               for key,value in [key_value.split(dict_del)
                                                 for key_value in self.ccode_str.split(twin_del)]}
        prinf('currency_symbols = %s', self.currency_symbols)


    def __init_currency_symbols_from_xe__(self):
        # not implemented
        self.base_url = 'http://www.xe.com/symbols.php'
        self.response = requests.get(self.base_url)
        if not self.response:
            prinf(self.response)
            return None

        #beautifulSoup
        #a = self.response.json()['currencySymblTable']
        #prinf(a)

    def get_currency_code(self, currency_str):
        if len(currency_str) == 3:
            if all([char.isupper() for char in currency_str]):
                # the currency_str has 3 chars and its all upper letters
                # - according to http://www.xe.com/symbols.php it is probably currency code
                return currency_str

        if self.currency_symbols is None:
            self.init_currency_symbols()

        ccode = self.currency_symbols.get(currency_str, None)
        if ccode:
            return ccode
        else:
            prine('Currency symbol [%s] is not in our database.', self.currency_str)
            return None

