"""This module contains all configuration information used to run simulations
"""
from multiprocessing import cpu_count
from collections import deque
import copy
from icarus.util import Tree

# GENERAL SETTINGS

# Level of logging output
# Available options: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL = 'INFO'

# If True, executes simulations in parallel using multiple processes
# to take advantage of multicore CPUs
PARALLEL_EXECUTION = False

# Number of processes used to run simulations in parallel.
# This option is ignored if PARALLEL_EXECUTION = False
N_PROCESSES = cpu_count()

# Granularity of caching.
# Currently, only OBJECT is supported
CACHING_GRANULARITY = 'OBJECT'

# Format in which results are saved.
# Result readers and writers are located in module ./icarus/results/readwrite.py
# Currently only PICKLE is supported
RESULTS_FORMAT = 'PICKLE'

# Number of times each experiment is replicated
# This is necessary for extracting confidence interval of selected metrics
N_REPLICATIONS = 1

# List of metrics to be measured in the experiments
# The implementation of data collectors are located in ./icarus/execution/collectors.py
DATA_COLLECTORS = ['CACHE_HIT_RATIO', 'LATENCY']

# Range of alpha values of the Zipf distribution using to generate content requests
# alpha values must be positive. The greater the value the more skewed is the
# content popularity distribution
# Range of alpha values of the Zipf distribution using to generate content requests
# alpha values must be positive. The greater the value the more skewed is the
# content popularity distribution
# Note: to generate these alpha values, numpy.arange could also be used, but it
# is not recommended because generated numbers may be not those desired.:q
# E.g. arange may return 0.799999999999 instead of 0.8.
# This would give problems while trying to plot the results because if for
# example I wanted to filter experiment with alpha=0.8, experiments with
# alpha = 0.799999999999 would not be recognized
ALPHA = [0.6, 0.8, 1, 1.2, 1.4, 1.6, 1.8]
# ALPHA = [1]

# Total size of network cache as a fraction of content population
NETWORK_CACHE = [0.004, 0.01, 0.05, 0.1, 0.3, 0.5]
# NETWORK_CACHE = [0.1]

# Number of content objects
N_CONTENTS = 3 * 10 ** 4

# Number of requests per second (over the whole network)
NETWORK_REQUEST_RATE = 10.0

# Number of content requests generated to prepopulate the caches
# These requests are not logged
N_WARMUP_REQUESTS = 3 * 10 ** 4

# Number of content requests generated after the warmup and logged
# to generate results.
N_MEASURED_REQUESTS = 6 * 10 ** 4

# DELAY_PENALTY = 1000 / NETWORK_REQUEST_RATE
DELAY_PENALTY = 0

CACHE_QUEUE_SIZE = 1

# List of all implemented topologies
# Topology implementations are located in ./icarus/scenarios/topology.py
TOPOLOGIES = [
        'PATH'
              ]

# List of caching and routing strategies
# The code is located in ./icarus/models/strategy.py


STRATEGIES1 = [
     'LCE_PKT_LEVEL',  # Leave Copy Everywhere
     # 'NO_CACHE',  # No caching, shorest-path routing
     'LCD_PKT_LEVEL',  # Leave Copy Down
     'PROB_CACHE_PKT_LEVEL'  # ProbCache packet level cache delay
     # 'PROB_CACHE_PL_CD'   # LCE packet level cache delay
              ]
STRATEGIES2= [
        'LCE_PL_CD',
        'LCD_PL_CD',
        'PROB_CACHE_PL_CD'
        ]

STRATEGIES = STRATEGIES1 + STRATEGIES2

# Cache replacement policy used by the network caches.
# Supported policies are: 'LRU', 'LFU', 'FIFO', 'RAND' and 'NULL'
# Cache policy implmentations are located in ./icarus/models/cache.py
CACHE_POLICY = 'LRU'

# Queue of experiments
EXPERIMENT_QUEUE = deque()
default = Tree()
default['workload'] = {'n_contents': N_CONTENTS,
                       'n_warmup':   N_WARMUP_REQUESTS,
                       'n_measured': N_MEASURED_REQUESTS,
                       'rate':       NETWORK_REQUEST_RATE,
                       'delay_penalty': DELAY_PENALTY,
                       'cache_queue_size': CACHE_QUEUE_SIZE
                       }
default['cache_placement']['name'] = 'UNIFORM'
default['content_placement']['name'] = 'UNIFORM'
default['cache_policy']['name'] = CACHE_POLICY

# Set topology
default['topology']['name'] = 'PATH'
default['topology']['n'] = 3
default['topology']['delay'] = 2

# Create experiments multiplexing all desired parameters
for alpha in ALPHA:
    for strategy in STRATEGIES2:
        # for topology in TOPOLOGIES:
        for network_cache in NETWORK_CACHE:
            experiment = copy.deepcopy(default)
            experiment['workload']['name'] = 'STATIONARY_PACKET_LEVEL_CACHE_DELAY'
            experiment['workload']['alpha'] = alpha
            experiment['workload']['delay_penalty'] = DELAY_PENALTY
            experiment['workload']['cache_queue_size'] = CACHE_QUEUE_SIZE
            experiment['strategy']['name'] = strategy
            # experiment['topology']['name'] = topology
            experiment['cache_placement']['network_cache'] = network_cache
            experiment['desc'] = "Alpha: %s, strategy: %s, topology: %s, network cache: %s" \
                    % (str(alpha), strategy, TOPOLOGIES[0], str(network_cache))
            EXPERIMENT_QUEUE.append(experiment)

for alpha in ALPHA:
    for strategy in STRATEGIES1:
        # for topology in TOPOLOGIES:
        for network_cache in NETWORK_CACHE:
            experiment = copy.deepcopy(default)
            experiment['workload']['name'] = 'STATIONARY_PACKET_LEVEL'
            experiment['workload']['alpha'] = alpha
            experiment['strategy']['name'] = strategy
            # experiment['topology']['name'] = topology
            experiment['cache_placement']['network_cache'] = network_cache
            experiment['desc'] = "Alpha: %s, strategy: %s, topology: %s, network cache: %s" \
                    % (str(alpha), strategy, TOPOLOGIES[0], str(network_cache))
            EXPERIMENT_QUEUE.append(experiment)















