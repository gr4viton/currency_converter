import arrow

class CurrencyConverterSite():
    def __init__(self, name, base, strs):
        self.name = name
        self.base = base
        self.strs = strs

    def create_url(self):
        pass

    def create_params(self):
        pass

    def get_response(self):
        pass

    def get_this_rate_for_ccode(self, in_ccode, my_params={}):
        pass

    def get_these_rates_for_ccode(self, in_ccode, my_params={}):
        pass

    def get_all_rates_for_ccode(self, in_ccode, my_params={}):
        pass

    def get_rates_for(self, in_ccode, my_params={}):
        self.base_url = self.base

        def _add_path_(try_jpn):
            part = self.strs.get(try_jpn, None)
            if part:
                self.base_url += part
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


        if _add_param_(jpn.var_date):
            curdate = arrow.now().format(self.strs[jpn.var_date_format])
            print(curdate)
            _add_param_(jpn.var_date, var=curdate)
            pass

        # get server output
        print(self.base_url, my_params)
        response = requests.get(self.base_url, params=my_params)

        if not response:
            print(response)
            return None
        else:
            if response.status_code > 400 :
                print(self.name, 'currency converter site response not found. ', response.status_code)
                return None
            elif response.status_code == 200:
                print(response.json())


        results = response.json()[self.strs[jpn.key_output]]
        self.output = [in_ccode, results]
        return self.output


    def get_some_rates_for(self, in_ccode, out_ccode_str, my_params={}):
        my_params.update({self.strs[jpn.var_out_ccode] : out_ccode_str})
        return self.get_rates_for(in_ccode, my_params=my_params)


    # def __str__(self):
    #     text =
    #     return text
    #

    @staticmethod
    def new_rates_available(utc_old, utc_now=None):
        return False