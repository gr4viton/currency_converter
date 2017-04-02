import enum

class AutoNumber(enum.Enum):
    def __new__(cls):
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

class JsonParameterNames(AutoNumber):
    """
    DataDictParameterNames == dd
    """


    key_input = () # string for input dictionary title
    key_in_amount = () # string for input amount title
    key_in_ccode = () # string for input currency code title
    var_in_ccode = () # json variable for input currency code

    key_output = () # string for output dictionary title
    key_out_amount = () # string for output amount title (usually not used)
    key_out_ccode = () # string for output currency code title (usually not used)
    var_out_ccode = () # json variable for output currency code - exchange rates output currency codes selection

    path_latest = ()
    path_all_rates = ()

    var_apikey = ()
    free_apikey = ()
    paid_apikey = ()




# ./currency_converter.py --amount 100.0 --input_currency EUR --output_currency CZK
# {
#     "input": {
#         "amount": 100.0,
#         "currency": "EUR"
#     },
#     "output": {
#         "CZK": 2707.36,
#     }
# }

# http://api.fixer.io/latest?symbols=USD,GBP
# {
#     "base": "EUR",
#     "date": "2017-03-31",
#     "rates": {
#         "GBP": 0.85553,
#         "USD": 1.0691
#     }
# }