#!/bin/env python2

import operator
import sys

import collections
import matplotlib.pyplot as plt
from oslo.config import cfg
from oslo.db.sqlalchemy import utils as db_utils
import pandas as pd

from subunit2sql.db import api
from subunit2sql.db import models
from subunit2sql import shell

CONF = cfg.CONF

SHELL_OPTS = [
    cfg.StrOpt('test_id', positional=True, required=True,
               help='Test id to extract time series for'),
]

def cli_opts():
    for opt in SHELL_OPTS:
        CONF.register_cli_opt(opt)


def list_opts():
    opt_list = copy.deepcopy(SHELL_OPTS)
    return [('DEFAULT', opt_list)]


def generate_series(test_id):
    session = api.get_session()
    run_times = api.get_test_run_time_series(test_id, session)
    session.close()
    ts = pd.Series(run_times)

#    ts = ts.truncate(after='11/26/2014')
#    print len(ts)
#    plot1 = pd.rolling_median(test, 100).plot()
    plot = pd.rolling_mean(ts, 50).plot()
    plot = ts.plot()
    fig = plot.get_figure()
    fig.savefig('/tmp/test.eps')
    return ts

def get_metadata(id):
    session = api.get_session()
    query = db_utils.model_query(models.Test, session=session).filter_by(
        id=id).join(models.TestRun).filter_by(status='success').join(
            models.RunMetadata,
            models.RunMetadata.run_id==models.TestRun.run_id).values(
                models.TestRun.start_time,
                models.TestRun.stop_time,
                models.RunMetadata.key,
                models.RunMetadata.value,
                models.TestRun.status)

    test_times = {}
    valid_keys = ['build_node', 'build_name']
    for run in query:
        if run[4] != 'success':
            continue
        if run[0] not in test_times:
            run_time = (run[1] - run[0]).total_seconds()
            metadata = {run[2]: run[3]}
            test_times[run[0]] = (run_time, metadata)
        else:
            test_times[run[0]][1][run[2]] = run[3]

    metas = {}
    metas_more = {}
    metas_really_slow = {}
    count = 0
    count_more = 0
    count_really_slow = 0
    dates = []
    series = {}
    series_more = {}
    series_really_slow = {}
    for run in test_times:
        if test_times[run][0] < 100:
            if 'build_queue' in test_times[run][1]:
                if test_times[run][1]['build_queue'] != 'gate':
                    continue
            if 'build_branch' in test_times[run][1]:
                if test_times[run][1]['build_branch'] == 'master':
                    continue
            count = count + 1
            for meta in test_times[run][1]:
                if meta in metas:
                    metas[meta].append(test_times[run][1].get(meta))
                else:
                    metas[meta] = [test_times[run][1].get(meta)]
                dates.append(run)
            series[run] = test_times[run][0]
        elif test_times[run][0] >= 100:
            if test_times[run][0] >= 175:
                if 'build_queue' in test_times[run][1]:
                    if test_times[run][1]['build_queue'] != 'gate':
                        continue
                if 'build_branch' in test_times[run][1]:
                    if test_times[run][1]['build_branch'] != 'master':
                        continue
                count_really_slow = count_really_slow + 1
                for meta in test_times[run][1]:
                    if meta in metas_really_slow:
                        metas_really_slow[meta].append(test_times[run][1].get(meta))
                    else:
                        metas_really_slow[meta] = [test_times[run][1].get(meta)]
                series_really_slow[run] = test_times[run][0]
            else:
                if 'build_queue' in test_times[run][1]:
                    if test_times[run][1]['build_queue'] != 'gate':
                        continue
                if 'build_branch' in test_times[run][1]:
                    if test_times[run][1]['build_branch'] != 'master':
                        continue
                count_more = count_more + 1
                for meta in test_times[run][1]:
                    if meta in metas_more:
                        metas_more[meta].append(test_times[run][1].get(meta))
                    else:
                        metas_more[meta] = [test_times[run][1].get(meta)]
                series_more[run] = test_times[run][0]
    vals = {}
    trusty = 0
    precise = 0
    other = 0
    vals_more = {}
    trusty_more = 0
    precise_more = 0
    other_more = 0
    vals_really_slow = {}
    hp_really_slow = 0
    rax_really_slow = 0
    other_really_slow = 0
    for meta in metas:
        if meta == 'build_node':
            for node in metas[meta]:
                if 'trusty' in node:
                    trusty = trusty + 1
                elif 'precise' in node:
                    precise = precise + 1
                else:
                    other = other + 1
        else:
            vals[meta] = dict(collections.Counter(metas[meta]))
    for meta in metas_more:
        if meta == 'build_node':
            for node in metas_more[meta]:
                if 'hp' in node:
                    trusty_more = trusty_more + 1
                elif 'rax' in node:
                    precise_more = precise_more + 1
                else:
                    other_more = other_more + 1
        else:
            vals_more[meta] = dict(collections.Counter(metas_more[meta]))

    for meta in metas_really_slow:
        if meta == 'build_node':
            for node in metas_really_slow[meta]:
                if 'hp' in node:
                    hp_really_slow = hp_really_slow + 1
                elif 'rax' in node:
                    rax_really_slow = rax_really_slow + 1
                else:
                    other_really_slow = other_really_slow + 1
        else:
            vals_really_slow[meta] = dict(collections.Counter(metas_really_slow[meta]))
    print "Fast Jobs:"
    print 'Build Queues:'
    print vals['build_queue']
#    print 'Build Name'
#    print vals['build_name']
    print 'Build Branch'
    print vals['build_branch']
    print "trusty: %s, precise %s, other: %s" % (trusty, precise, other)
    print max(dates)
    print "Slow Jobs:"
    print 'Build Queues:'
    print vals_more['build_queue']
#    print 'Build Name'
#    print vals_more['build_name']
    print 'Build Branch'
    print vals_more['build_branch']
    print "hp: %s, rax %s, other: %s" % (trusty_more, precise_more, other_more)
    print sorted(vals_more['build_name'].items(), key=operator.itemgetter(1))
    print "Really Slow Jobs:"
    print 'Build Queues:'
    print sorted(vals_really_slow['build_queue'].items(), key=operator.itemgetter(1))
#    print 'Build Name'
#    print vals_more['build_name']
    print 'Build Branch'
    print vals_really_slow['build_branch']
    print "hp: %s, rax %s, other: %s" % (hp_really_slow, rax_really_slow, other_really_slow)
    print sorted(vals_really_slow['build_name'].items(), key=operator.itemgetter(1))

    ts_slow = pd.Series(series_more)
    ts = pd.Series(series)
    ts_really_slow = pd.Series(series_really_slow)
#    plot = pd.rolling_mean(ts_slow, 60).plot()
    plot = pd.rolling_mean(ts_slow, 60).plot()
    plot2 = pd.rolling_mean(ts, 8).plot()
    plot3 = pd.rolling_mean(ts_really_slow, 10).plot()
    fig = plot.get_figure()
    fig.savefig('/tmp/test2.png')


def main():
    cli_opts()
    shell.parse_args(sys.argv)
    run_times = generate_series(CONF.test_id)
    
    # NOTE(mtreinish) This call was used to investigate the split in run times
    # on test_rescued_vm_detach_volume which shows clear splits in performance
    #get_metadata(CONF.test_id)


if __name__ == "__main__":
    sys.exit(main())
