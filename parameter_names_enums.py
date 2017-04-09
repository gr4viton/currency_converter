import enum


class AutoNumber(enum.Enum):
    """Auto-numbering class for enums

    Every class inheriting from AutoNumber, will have its keys inumerated automatically
    if initialized as empty tuple. e.g
    a = ()
    """
    def __new__(cls):
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._value_ = value
        return obj


class JsonParameterNames(AutoNumber):
    """Enumeration class for parameters of json response keys (key) and url-variables (var)

    Default importing
    import JsonParameterNames from parameter_names_enums as jpn
    """

    key_input = ()  # string for input dictionary title
    key_in_amount = ()  # string for input amount title
    key_in_ccode = ()  # string for input currency code title
    var_in_ccode = ()  # json variable for input currency code

    key_output = ()  # string for output dictionary title
    key_out_amount = ()  # string for output amount title (usually not used)
    key_out_ccode = ()  # string for output currency code title (usually not used)
    var_out_ccode = ()  # json variable for output currency code - exchange rates output currency codes selection

    path_latest = ()  # url path to the latest exchange rates
    path_all_rates = () # url path to the all the exchange rates

    var_apikey = ()  # apikey variable in url
    free_apikey = ()  # free apikey string
    paid_apikey = ()  # paid apikey string

    var_date = ()  # url variable date name
    var_date_format = ()  # url variable date format e.g. 'YYYY-MM-DD'
    key_date = ()  # json date key name
    key_date_format = ()  # json date key format e.g. 'YYYY-MM-DD'


# not used while using redisworks
class RedisParameterNames(AutoNumber):
    """
    RedisParameterNames = rpn
    """

    csc_initialized = ()  # currency_symbol_converter_initialized