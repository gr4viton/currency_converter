import enum

class AutoNumber(enum.Enum):
    def __new__(cls):
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

class JsonParameterNames(AutoNumber):
    """
    JsonParameterNames = jpn
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

    var_date = ()
    var_date_format = ()
    key_date = ()
    key_date_format = ()



class RedisParameterNames(AutoNumber):
    """
    RedisParameterNames = rpn
    """

    csc_initialized = () # currency_symbol_converter_initialized