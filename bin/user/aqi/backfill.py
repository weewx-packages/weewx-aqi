#!/usr/bin/env python
# weewx-aqi
# Copyright 2018 - Jonathan Koren <jonathan@jonathankoren.com>
# Modified 2026-10-22: read actual archive columns without opening station hardware.
# License: GPL 3

import argparse
import sys
from types import SimpleNamespace

import weecfg
import weewx
import weewx.manager
import user.aqi.service


def backfill(config, start_time=0, end_time=sys.maxsize):
    """Calculate AQI records for a timestamp range using the configured standard.

    Args:
        config (dict): WeeWX station and AQI configuration.
        start_time (int): First archive timestamp, included.
        end_time (int): Last archive timestamp, excluded.

    Returns:
        int: Number of weather archive records processed.
    """
    binder = weewx.manager.DBBinder(config)
    try:
        engine = SimpleNamespace(db_binder=binder, bind=lambda *args: None)
        extension = user.aqi.service.AqiService(engine, config)
        weather = binder.get_manager(data_binding='wx_binding')
        sql = 'SELECT dateTime, interval FROM %s WHERE dateTime >= ? AND dateTime < ? ORDER BY dateTime' % weather.table_name
        count = 0
        for timestamp, interval in weather.genSql(sql, (start_time, end_time)):
            extension.new_archive_record(weewx.Event(weewx.NEW_ARCHIVE_RECORD,
                record={'dateTime': timestamp, 'interval': interval}))
            count += 1
        return count
    finally:
        binder.close()


def main():
    parser = argparse.ArgumentParser(description='Backfill AQI from the configured archive and sensor bindings.')
    parser.add_argument('config_file', help='WeeWX configuration file')
    parser.add_argument('--start_time', type=int, default=0)
    parser.add_argument('--end_time', type=int, default=sys.maxsize)
    args = parser.parse_args()
    path, config = weecfg.read_config(args.config_file, [])
    print('Processed %d archive records' % backfill(config, args.start_time, args.end_time))


if __name__ == '__main__':
    main()
