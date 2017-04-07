# Currency converter - task from kiwi

Program for conversion from one currency to another

## Featuring
- smart internet connection and currency conversion sites response detection
-- currency conversion sites implemented: fixer.io
- offline currencies sql database on disk
-- automatic offline database update on detection of new rates update from any implemented site
--- data_valid_utc is stored separately in txt file - faster then another sql database query
- time effective conversion
-- tested on windows 64
--- w/o update offline database triggered : ~ 50 ms
--- else : ~ 1200ms
- standard logger for logging
- argparser for input argument parsing - help string autogeneration
- manually tested
-- 3 types input arguments from assignment <https://gist.github.com/MichalCab/3c94130adf9ec0c486dfca8d0f01d794>
-- another common currency symbols - Kč, $, CNY-symbol, GBP-symbol, EUR-symbol
- used modules:
-- pandas, sqlalchemy, redis, redisworks, requests, json
-- arrow, argparse
-- platform, socket, sys, time, pathlib, logging, pickle
- using decorators: staticmethod, classmethod

## Usage

### Parameters
- --amount - amount which we want to convert - float
- --input_currency - input currency - 3 letters name or currency symbol
- --output_currency - requested/output currency - 3 letters name or currency symbol


### OUTPUT
- json with following structure:
```
{
   "input": {
        "amount": <float>,
        "currency": <3 letter currency code>
    }
    "output": {
        <3 letter currency code>: <float>
    }
}
```

### Trigger online update
- to trigger offline sql disk database update from online cconversion sites
-- Declare global variable DEBUG with value including 'simulate_time'
--- This makes the [get_sites_states] function thing the time is 12 days in the future
--- Future date triggers the program to think new rates are available
-- Delete one or both files
--- db/rates_info.nfo = sql database valid_to date info
--- db/exchange_rates.db = sql database with offline rates

## Disclaimer
### Not using these controversial tricks to get lower latency
#### [x] Immediate exchange rate json output after reading (from sql/redis)
 - implemented style: First the program tries to find out if the database should be updated
 - not implemented: First run the program returns json data from offline database
  -- even if in second thread updating the database afterwards
  -- user gets better response time, but the first time he calls, he can get outdated rates
   --- we certainly do not want that on the first start after a long time (olddated sql database)
   --- it can be implemented w/o further ado, but only if the server with redis is updated frequently

### Not implemented (yet) - future releases maybe
- full redis support for rates
-- expire time - to the known time of next update from any implemented site
- automatic selection of cconversion site dependent on offered currency codes conversion
-- e.g if CZK is not in the most fresh currency converter site - it will not be converted to/from
- currency conversion rates from multiple sources in the offline database
-- e.g. if CZK is not in the selected most fresh currency converter site - it will not be converted to/from
- multithreading - load from database at start in different thread - use the data or not later
-- after finding the offline data are not fresh enough
- automatic database update as a background service
-- would update sql database and redis automatically not needed to check every time the convert is triggered
- automatic testing via asserts and node2 module
- user input error autocorrection
-- suggestion of the textually nearest currency
-- another program argument for automatic nearest suggestion conversion
-- localisation of output / logger texts into other languages
- modules to possibly use:
-- hiredis - can be 10 times faster on windows..
-- BeautifulSoup - for automatic currency symbol to currency code conversion from site <http://www.xe.com/symbols.php>

