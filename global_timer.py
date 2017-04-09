#!/usr/bin/python
# -*- coding: utf-8 -*-

import time
import logging

from logging import info as prinf
from logging import debug as prind
from logging import warning as prinw
from logging import error as prine

timers = {}

def g_start(timer_name=None):
    """Starts a global timer with a name"""
    if timer_name is None:
        timer_name = 'default'
    timers[timer_name] = time.time()

def g_end(text, timer_name=None):
    """Ends a global timer measurement and prinfs it"""
    if timer_name is None:
        timer_name = 'default'
    if timer_name not in timers.keys():
        prinw('%s timer_name not started yet.', timer_name)
        return -1
    sec = time.time() - timers[timer_name]
    ms = round(sec*1000, 2)
    prinf('%s ms %s', ms, text)
    return ms

if __name__ == '__main__':
    """Shows usage of named and unnamed global timers"""
    logging.basicConfig(level=logging.DEBUG)
    g_start()
    time.sleep(1)
    g_start('one_sec')
    time.sleep(1)
    g_end('two seconds default timer')
    g_end('one second one_sec timer', 'one_sec')