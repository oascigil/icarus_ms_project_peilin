#!/usr/bin/env python
"""Plot results read from a result set
"""
from __future__ import division
import os
import argparse
import logging

import matplotlib.pyplot as plt

from icarus.util import Settings, config_logging
from icarus.results import plot_lines, plot_bar_chart
from icarus.registry import RESULTS_READER


# Logger object
logger = logging.getLogger('plot')

# These lines prevent insertion of Type 3 fonts in figures
# Publishers don't want them
plt.rcParams['ps.useafm'] = True
plt.rcParams['pdf.use14corefonts'] = True

# If True text is interpreted as LaTeX, e.g. underscore are interpreted as
# subscript. If False, text is interpreted literally
plt.rcParams['text.usetex'] = False

# Aspect ratio of the output figures
plt.rcParams['figure.figsize'] = 8, 5

# Size of font in legends
LEGEND_SIZE = 14

# Line width in pixels
LINE_WIDTH = 1.5

# Plot
PLOT_EMPTY_GRAPHS = True

# This dict maps strategy names to the style of the line to be used in the plots
# Off-path strategies: solid lines
# On-path strategies: dashed lines
# No-cache: dotted line
STRATEGY_STYLE = {
         'LCE_PKT_LEVEL':             'k--o',
         'LCD_PKT_LEVEL':             'r--v',
         'PROB_CACHE_PKT_lEVEL':      'c--s',
         'LCE_AVOID_BUSY_NODE':             'k--o',
         'LCD_AVOID_BUSY_NODE':             'r--v',
         'PROB_CACHE_AVOID_BUSY_NODE':      'c--s',
         'LCE_PL_CD':                 'k-o',
         'LCD_PL_CD':                 'r-v',
         'PROB_CACHE_PL_CD':          'c-s'
                }

# This dict maps name of strategies to names to be displayed in the legend
STRATEGY_LEGEND = {
         'LCE_PKT_LEVEL':             'LCE packet level',
         'LCD_PKT_LEVEL':             'LCD packet level',
         'PROB_CACHE_PKT_LEVEL':      'ProbCache packet level',
         'LCE_AVOID_BUSY_NODE':             'LCE packet level avoid busy node',
         'LCD_AVOID_BUSY_NODE':             'LCD packet level avoid busy node',
         'PROB_CACHE_AVOID_BUSY_NODE':      'ProbCache packet level avoid busy node',
         'LCE_PL_CD':                 'LCE packet level add cache delay',
         'LCD_PL_CD':                 'LCD packet level add cache delay',
         'PROB_CACHE_PL_CD':          'ProbCache packet level add cache delay'  
                    }

# Color and hatch styles for bar charts of cache hit ratio and link load vs topology
STRATEGY_BAR_COLOR = {
    'LCE_PKT_LEVEL':            '0.1',
    'LCD_PKT_LEVEL':            '0.3',
    'PROB_CACHE_PKT_LEVEL':     '0.5', 
    'LCE_AVOID_BUSY_NODE':            'k',
    'LCD_AVOID_BUSY_NODE':            '0.2',
    'PROB_AVOID_BUSY_NODE':           '0.4',
    'LCE_PL_CD':                '0.6',
    'LCD_PL_CD':                '0.7',
    'PROB_CACHE_PL_CD':         '0.9'
    }

STRATEGY_BAR_HATCH = {
    'LCE_PKT_LEVEL':              'o',
    'LCD_PKT_LEVEL':              '//',
    'PROB_CACHE_PKT_LEVEL':       '+',
    'LCE_AVOID_BUSY_NODE':              'o',
    'LCD_AVOID_BUSY_NODE':              '//',
    'PROB_CACHE_AVOID_BUSY_NODE':       None,
    'LCE_PL_CD':                  'o',
    'LCD_PL_CD':                  '//',
    'PROB_CACHE_PL_CD':           '+'
    }


def plot_cache_hits_vs_alpha(resultset, topology, cache_size, alpha_range, strategies, plotdir):
    # if 'NO_CACHE' in strategies:
        # strategies.remove('NO_CACHE')
    desc = {}
    print(resultset)
    desc['title'] = 'Cache hit ratio: T=%s C=%s' % (topology, cache_size)
    desc['ylabel'] = 'Cache hit ratio'
    desc['xlabel'] = 'Content distribution parameter'
    desc['xparam'] = ('workload', 'alpha')
    desc['xvals'] = alpha_range
    desc['filter'] = {'topology': {'name': topology},
                      'cache_placement': {'network_cache': cache_size}}
    desc['ymetrics'] = [('CACHE_HIT_RATIO', 'MEAN')] * len(strategies)
    desc['ycondnames'] = [('strategy', 'name')] * len(strategies)
    desc['ycondvals'] = strategies
    desc['errorbar'] = True
    desc['legend_loc'] = 'upper left'
    desc['line_style'] = STRATEGY_STYLE
    desc['legend'] = STRATEGY_LEGEND
    desc['plotempty'] = PLOT_EMPTY_GRAPHS
    plot_lines(resultset, desc, 'CACHE_HIT_RATIO_T=%s@C=%s.pdf'
               % (topology, cache_size), plotdir)


def plot_cache_hits_vs_cache_size(resultset, topology, alpha, cache_size_range, strategies, plotdir):
    desc = {}
    # if 'NO_CACHE' in strategies:
        # strategies.remove('NO_CACHE')
    desc['title'] = 'Cache hit ratio: T=%s A=%s' % (topology, alpha)
    desc['xlabel'] = u'Cache to population ratio'
    desc['ylabel'] = 'Cache hit ratio'
    # desc['xscale'] = 'log'
    desc['xparam'] = ('cache_placement', 'network_cache')
    desc['xvals'] = cache_size_range
    desc['filter'] = {'topology': {'name': topology},
                      # 'workload': {'name': 'STATIONARY_PACKET_LEVEL', 'alpha': alpha}}
                      'workload': {'alpha': alpha}}       
    desc['ymetrics'] = [('CACHE_HIT_RATIO', 'MEAN')] * len(strategies)
    desc['ycondnames'] = [('strategy', 'name')] * len(strategies)
    desc['ycondvals'] = strategies
    desc['errorbar'] = True
    desc['legend_loc'] = 'lower right'
    desc['line_style'] = STRATEGY_STYLE
    desc['legend'] = STRATEGY_LEGEND
    desc['plotempty'] = PLOT_EMPTY_GRAPHS
    plot_lines(resultset, desc, 'CACHE_HIT_RATIO_T=%s@A=%s.pdf'
               % (topology, alpha), plotdir)


def plot_latency_vs_alpha(resultset, topology, cache_size, alpha_range, strategies, plotdir):
    desc = {}
    desc['title'] = 'Latency: T=%s C=%s' % (topology, cache_size)
    desc['xlabel'] = 'Content distribution parameter'
    desc['ylabel'] = 'Latency (ms)'
    desc['xparam'] = ('workload', 'alpha')
    desc['xvals'] = alpha_range
    desc['filter'] = {'topology': {'name': topology},
                      'cache_placement': {'network_cache': cache_size}}
    desc['ymetrics'] = [('LATENCY', 'MEAN')] * len(strategies)
    desc['ycondnames'] = [('strategy', 'name')] * len(strategies)
    desc['ycondvals'] = strategies
    desc['errorbar'] = True
    desc['legend_loc'] = 'center left'
    desc['line_style'] = STRATEGY_STYLE
    desc['legend'] = STRATEGY_LEGEND
    desc['plotempty'] = PLOT_EMPTY_GRAPHS
    plot_lines(resultset, desc, 'LATENCY_T=%s@C=%s.pdf'
               % (topology, cache_size), plotdir)

def plot_latency_vs_cache_size(resultset, topology, alpha, cache_size_range, strategies, plotdir):
    desc = {}
    desc['title'] = 'Latency: T=%s A=%s' % (topology, alpha)
    desc['xlabel'] = u'Cache to population ratio'
    desc['ylabel'] = 'Latency (ms)'
    # desc['xscale'] = 'log'
    desc['xparam'] = ('cache_placement', 'network_cache')
    desc['xvals'] = cache_size_range
    desc['filter'] = {'topology': {'name': topology},
                      # 'workload': {'name': 'STATIONARY_PACKET_LEVEL', 'alpha': alpha}
                      'workload': {'alpha': alpha}}
    desc['ymetrics'] = [('LATENCY', 'MEAN')] * len(strategies)
    desc['ycondnames'] = [('strategy', 'name')] * len(strategies)
    desc['ycondvals'] = strategies
    # desc['metric'] = ('LATENCY', 'MEAN')
    desc['errorbar'] = True
    desc['legend_loc'] = 'center left'
    desc['line_style'] = STRATEGY_STYLE
    desc['legend'] = STRATEGY_LEGEND
    desc['plotempty'] = PLOT_EMPTY_GRAPHS
    plot_lines(resultset, desc, 'LATENCY_T=%s@A=%s.pdf'
               % (topology, alpha), plotdir)



def plot_cache_hits_vs_topology(resultset, alpha, cache_size, topology_range, strategies, plotdir):
    """
    Plot bar graphs of cache hit ratio for specific values of alpha and cache
    size for various topologies.

    The objective here is to show that our algorithms works well on all
    topologies considered
    """
    # if 'NO_CACHE' in strategies:
        # strategies.remove('NO_CACHE')
    desc = {}
    desc['title'] = 'Cache hit ratio: A=%s C=%s' % (alpha, cache_size)
    desc['ylabel'] = 'Cache hit ratio'
    desc['xparam'] = ('topology', 'name')
    desc['xvals'] = topology_range
    desc['filter'] = {'cache_placement': {'network_cache': cache_size},
                      # 'workload': {'name': 'STATIONARY', 'alpha': alpha}
                      'workload': {'alpha': alpha}}
    desc['ymetrics'] = [('CACHE_HIT_RATIO', 'MEAN')] * len(strategies)
    desc['ycondnames'] = [('strategy', 'name')] * len(strategies)
    desc['ycondvals'] = strategies
    desc['errorbar'] = True
    desc['legend_loc'] = 'lower right'
    desc['bar_color'] = STRATEGY_BAR_COLOR
    desc['bar_hatch'] = STRATEGY_BAR_HATCH
    desc['legend'] = STRATEGY_LEGEND
    desc['plotempty'] = PLOT_EMPTY_GRAPHS
    plot_bar_chart(resultset, desc, 'CACHE_HIT_RATIO_A=%s_C=%s.pdf'
                   % (alpha, cache_size), plotdir)

def plot_cache_hits_vs_server_processing_rate(resultset, topology, cache_size, alpha, server_rate_range, strategies, plotdir):
    desc = {}
    desc['title'] = 'Cache hit ratio: T=%s C=%s A=%s' % (topology, cache_size, alpha)
    desc['xlabel'] = 'Server processing rate'
    desc['ylabel'] = 'Cache hit ratio'
    desc['xparam'] = ('workload', 'server_processing_rate')
    desc['xvals'] = server_rate_range
    desc['filter'] = {'topology': {'name': topology},
                      'cache_placement': {'network_cache': cache_size},
                      'workload': {'alpha': alpha}}
    desc['ymetrics'] = [('CACHE_HIT_RATIO', 'MEAN')] * len(strategies)
    desc['ycondnames'] = [('strategy', 'name')] * len(strategies)
    desc['ycondvals'] = strategies
    desc['errorbar'] = True
    desc['legend_loc'] = 'upper right'
    desc['line_style'] = STRATEGY_STYLE
    desc['legend'] = STRATEGY_LEGEND
    desc['plotempty'] = PLOT_EMPTY_GRAPHS
    plot_lines(resultset, desc, 'CACHE_HIT_RATIO_T=%s@C=%s@A=%s.pdf'
               % (topology, cache_size, alpha), plotdir)

def plot_latency_vs_server_processing_rate(resultset, topology, cache_size, alpha, server_rate_range, strategies, plotdir):
    desc = {}
    desc['title'] = 'Latency: T=%s C=%s A=%s' % (topology, cache_size, alpha)
    desc['xlabel'] = 'Server processing rate'
    desc['ylabel'] = 'Latency (ms)'
    desc['xparam'] = ('workload', 'server_processing_rate')
    desc['xvals'] = server_rate_range
    desc['filter'] = {'topology': {'name': topology},
                      'cache_placement': {'network_cache': cache_size},
                      'workload': {'alpha': alpha}}
    desc['ymetrics'] = [('LATENCY', 'MEAN')] * len(strategies)
    desc['ycondnames'] = [('strategy', 'name')] * len(strategies)
    desc['ycondvals'] = strategies
    desc['errorbar'] = True
    desc['legend_loc'] = 'upper right'
    desc['line_style'] = STRATEGY_STYLE
    desc['legend'] = STRATEGY_LEGEND
    desc['plotempty'] = PLOT_EMPTY_GRAPHS
    plot_lines(resultset, desc, 'LATENCY_T=%s@C=%s@A=%s.pdf'
               % (topology, cache_size, alpha), plotdir)


def plot_percentage_of_rejection(resultset, topology, alpha, cache_size, n, strategies, plotdir):
    print('in plot rejected')
    desc = {}
    desc['title'] = 'Percentage of rejected packet: T=%s C=%s A=%s' % (topology, cache_size, alpha)
    desc['xlabel'] = u'node'
    desc['ylabel'] = 'Percentage of rejected packet'
    # desc['xscale'] = 'log'
    desc['xparam'] = ('topology', 'n')
    desc['xvals'] = n
    desc['filter'] = {'topology': {'name': topology},
                      # 'workload': {'name': 'STATIONARY_PACKET_LEVEL', 'alpha': alpha}
                      'workload': {'alpha': alpha},
                      'cache_placement': {'network_cache': cache_size}}
    desc['ymetrics'] = [('CACHE_QUEUE', 'PERCENTAGE_OF_REJECTION')] * len(strategies)
    desc['ycondnames'] = [('strategy', 'name')] * len(strategies)
    desc['ycondvals'] = strategies
    # desc['metric'] = ('LATENCY', 'MEAN')
    desc['errorbar'] = True
    desc['legend_loc'] = 'upper right'
    desc['line_style'] = STRATEGY_STYLE
    desc['legend'] = STRATEGY_LEGEND
    desc['plotempty'] = PLOT_EMPTY_GRAPHS
    plot_lines(resultset, desc, 'TOTAL_REJECTED_T=%s@C=%s@A=%s.pdf'
               % (topology, cache_size, alpha), plotdir)

def plot_percentage_of_request_rejection(resultset, topology, alpha, cache_size, n, strategies, plotdir):
    print('in plot rejected')
    desc = {}
    desc['title'] = 'Percentage of rejected request: T=%s C=%s A=%s' % (topology, cache_size, alpha)
    desc['xlabel'] = u'node'
    desc['ylabel'] = 'Percentage of rejected request'
    # desc['xscale'] = 'log'
    desc['xparam'] = ('topology', 'n')
    desc['xvals'] = n
    desc['filter'] = {'topology': {'name': topology},
                      # 'workload': {'name': 'STATIONARY_PACKET_LEVEL', 'alpha': alpha}
                      'workload': {'alpha': alpha},
                      'cache_placement': {'network_cache': cache_size}}
    desc['ymetrics'] = [('CACHE_QUEUE', 'PERCENTAGE_OF_REQUEST_REJECTION')] * len(strategies)
    desc['ycondnames'] = [('strategy', 'name')] * len(strategies)
    desc['ycondvals'] = strategies
    # desc['metric'] = ('LATENCY', 'MEAN')
    desc['errorbar'] = True
    desc['legend_loc'] = 'upper right'
    desc['line_style'] = STRATEGY_STYLE
    desc['legend'] = STRATEGY_LEGEND
    desc['plotempty'] = PLOT_EMPTY_GRAPHS
    plot_lines(resultset, desc, 'REQUEST_REJECTED_T=%s@C=%s@A=%s.pdf'
               % (topology, cache_size, alpha), plotdir)


def plot_percentage_of_data_rejection(resultset, topology, alpha, cache_size, n, strategies, plotdir):
    print('in plot rejected')
    desc = {}
    desc['title'] = 'Percentage of rejected data: T=%s C=%s A=%s' % (topology, cache_size, alpha)
    desc['xlabel'] = u'node'
    desc['ylabel'] = 'Percentage of rejected data'
    # desc['xscale'] = 'log'
    desc['xparam'] = ('topology', 'n')
    desc['xvals'] = n
    desc['filter'] = {'topology': {'name': topology},
                      # 'workload': {'name': 'STATIONARY_PACKET_LEVEL', 'alpha': alpha}
                      'workload': {'alpha': alpha},
                      'cache_placement': {'network_cache': cache_size}}
    desc['ymetrics'] = [('CACHE_QUEUE', 'PERCENTAGE_OF_DATA_REJECTION')] * len(strategies)
    desc['ycondnames'] = [('strategy', 'name')] * len(strategies)
    desc['ycondvals'] = strategies
    # desc['metric'] = ('LATENCY', 'MEAN')
    desc['errorbar'] = True
    desc['legend_loc'] = 'upper right'
    desc['line_style'] = STRATEGY_STYLE
    desc['legend'] = STRATEGY_LEGEND
    desc['plotempty'] = PLOT_EMPTY_GRAPHS
    plot_lines(resultset, desc, 'DATA_REJECTED_T=%s@C=%s@A=%s.pdf'
               % (topology, cache_size, alpha), plotdir)

def plot_cache_queue_size(resultset, topology, alpha, cache_size, n, strategies, plotdir):
    print('in plot queue size')
    desc = {}
    desc['title'] = 'Average cache queue size: T=%s C=%s A=%s' % (topology, cache_size, alpha)
    desc['xlabel'] = u'node'
    desc['ylabel'] = 'Average cache queue size'
    # desc['xscale'] = 'log'
    desc['xparam'] = ('topology', 'n')
    desc['xvals'] = n
    desc['filter'] = {'topology': {'name': topology},
                      # 'workload': {'name': 'STATIONARY_PACKET_LEVEL', 'alpha': alpha}
                      'workload': {'alpha': alpha},
                      'cache_placement': {'network_cache': cache_size}}
    desc['ymetrics'] = [('CACHE_QUEUE', 'AVERAGE_QUEUE_SIZE')] * len(strategies)
    desc['ycondnames'] = [('strategy', 'name')] * len(strategies)
    desc['ycondvals'] = strategies
    # desc['metric'] = ('LATENCY', 'MEAN')
    desc['errorbar'] = True
    desc['legend_loc'] = 'upper right'
    desc['line_style'] = STRATEGY_STYLE
    desc['legend'] = STRATEGY_LEGEND
    desc['plotempty'] = PLOT_EMPTY_GRAPHS
    plot_lines(resultset, desc, 'QUEUE_SIZE_T=%s@C=%s@A=%s.pdf'
               % (topology, cache_size, alpha), plotdir)


def run(config, results, plotdir):
    """Run the plot script

    Parameters
    ----------
    config : str
        The path of the configuration file
    results : str
        The file storing the experiment results
    plotdir : str
        The directory into which graphs will be saved
    """
    settings = Settings()
    settings.read_from(config)
    config_logging(settings.LOG_LEVEL)
    resultset = RESULTS_READER[settings.RESULTS_FORMAT](results)
    # Create dir if not existsing
    if not os.path.exists(plotdir):
        os.makedirs(plotdir)
    # Parse params from settings
    topologies = settings.TOPOLOGIES
    cache_sizes = settings.NETWORK_CACHE
    alphas = settings.ALPHA
    strategies = settings.STRATEGIES
    # server_processing_rates = settings.SERVER_PROCESSING_RATE
    print(strategies)
    # Plot graphs
    for topology in topologies:
        for cache_size in cache_sizes:
            logger.info('Plotting cache hit ratio for topology %s and cache size %s vs alpha' % (topology, str(cache_size)))
            plot_cache_hits_vs_alpha(resultset, topology, cache_size, alphas, strategies, plotdir)
            # logger.info('Plotting link load for topology %s vs cache size %s' % (topology, str(cache_size)))
            # plot_link_load_vs_alpha(resultset, topology, cache_size, alphas, strategies, plotdir)
            logger.info('Plotting latency for topology %s vs cache size %s' % (topology, str(cache_size)))
            plot_latency_vs_alpha(resultset, topology, cache_size, alphas, strategies, plotdir)
    for topology in topologies:
        for alpha in alphas:
            logger.info('Plotting cache hit ratio for topology %s and alpha %s vs cache size' % (topology, str(alpha)))
            plot_cache_hits_vs_cache_size(resultset, topology, alpha, cache_sizes, strategies, plotdir)
            # logger.info('Plotting link load for topology %s and alpha %s vs cache size' % (topology, str(alpha)))
            # plot_link_load_vs_cache_size(resultset, topology, alpha, cache_sizes, strategies, plotdir)
            logger.info('Plotting latency for topology %s and alpha %s vs cache size' % (topology, str(alpha)))
            plot_latency_vs_cache_size(resultset, topology, alpha, cache_sizes, strategies, plotdir)
    """
    for topology in topologies:
        for cache_size in cache_sizes:
            for alpha in alphas:
                # logger.info('Plotting cache hit ratio for topology %s cache size %s alpha %s vs server processing rate' % (topology, str(cache_size), str(alpha)))
                # plot_cache_hits_vs_server_processing_rate(resultset, topology, cache_size, alpha, server_processing_rates, strategies, plotdir)
                # logger.info('Plotting latency for topology %s cache size %s alpha %s vs server processing rate' % (topology, str(cache_size), str(alpha)))
                # plot_latency_vs_server_processing_rate(resultset, topology, cache_size, alpha, server_processing_rates, strategies, plotdir)
                logger.info('Plotting the percentage of packets arriving at a busy node')
                plot_percentage_of_rejection(resultset, topology, alpha, cache_size, n, strategies, plotdir)
                plot_percentage_of_request_rejection(resultset, topology, alpha, cache_size, n, strategies, plotdir)
                plot_percentage_of_data_rejection(resultset, topology, alpha, cache_size, n, strategies, plotdir)
                logger.info('Plotting average cache queue size')
                plot_cache_queue_size(resultset, topology, alpha, cache_size, n, strategies, plotdir)
    
    for cache_size in cache_sizes:
        for alpha in alphas:
            logger.info('Plotting cache hit ratio for cache size %s vs alpha %s against topologies' % (str(cache_size), str(alpha)))
            plot_cache_hits_vs_topology(resultset, alpha, cache_size, topologies, strategies, plotdir)
            # logger.info('Plotting link load for cache size %s vs alpha %s against topologies' % (str(cache_size), str(alpha)))
            # plot_link_load_vs_topology(resultset, alpha, cache_size, topologies, strategies, plotdir)
    """
    logger.info('Exit. Plots were saved in directory %s' % os.path.abspath(plotdir))


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("-r", "--results", dest="results",
                        help='the results file',
                        required=True)
    parser.add_argument("-o", "--output", dest="output",
                        help='the output directory where plots will be saved',
                        required=True)
    parser.add_argument("config",
                        help="the configuration file")
    args = parser.parse_args()
    run(args.config, args.results, args.output)


if __name__ == '__main__':
    main()
