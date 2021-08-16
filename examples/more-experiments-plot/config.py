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
DATA_COLLECTORS = ['CACHE_HIT_RATIO', 'LATENCY', 'CACHE_QUEUE']

# Range of alpha values of the Zipf distribution using to generate content requests
# alpha values must be positive. The greater the value the more skewed is the
# content popularity distribution
# Range of alpha values of the Zipf distribution using to generate content requests
# alpha values must be positive. The greater the value the more skewed is the
# content popularity distribution
# Note: to generate these alpha values, numpy.arange could also be used, but it
# is not recommended because generated numbers may be not those desired.
# E.g. arrange may return 0.799999999999 instead of 0.8.
# This would give problems while trying to plot the results because if for
# example I wanted to filter experiment with alpha=0.8, experiments with
# alpha = 0.799999999999 would not be recognized
ALPHA = [0.01, 0.05, 0.1, 0.2, 0.5, 0.8, 1, 1.4]
# ALPHA = [0.1]

# Total size of network cache as a fraction of content population
# NETWORK_CACHE = [0.004, 0.01, 0.05, 0.1, 0.3, 0.5]
NETWORK_CACHE = [0.1]

# Number of content objects
N_CONTENTS = 10 ** 3

# Number of requests per millisecond (over the whole network)
# The value 0.01 roughly represents 10 requests per second
# The value 0.04 roughly represents 40 requests per second
NETWORK_REQUEST_RATE = 0.04

# Number of content requests generated to prepopulate the caches
# These requests are not logged
N_WARMUP_REQUESTS = 5 * 10 ** 4

# Number of content requests generated after the warmup and logged
# to generate results.
N_MEASURED_REQUESTS = 10 ** 5

# READ_DELAY_PENALTY = 1/NETWORK_REQUEST_RATE
# WRITE_DELAY_PENALTY = 1/NETWORK_REQUEST_RATE
READ_DELAY_PENALTY = 100
WRITE_DELAY_PENALTY = 100
# SERVER_PROCESSING_RATE = [16, 13, 10, 7, 4]
# READ_DELAY_PENALTY = [1000/16, 1000/13, 1000/10, 1000/7, 1000/4]
# WRITE_DELAY_PENALTY = [1000/16, 1000/13, 1000/10, 1000/7, 1000/4]

CACHE_QUEUE_SIZE = 10


# List of caching and routing strategies
# The code is located in ./icarus/models/strategy.py


STRATEGIES1 = [
     # 'PROB_CACHE_PKT_LEVEL',  # ProbCache packet level cache delay
     # 'LCE_PKT_LEVEL',  # Leave Copy Everywhere
     # 'NO_CACHE',  # No caching, shorest-path routing
     # 'LCD_PKT_LEVEL'  # Leave Copy Down
              ]
STRATEGIES2= [
        'PROB_CACHE_PL_CD',
        'LCE_PL_CD',
        'LCD_PL_CD',
        'PROB_CACHE_AVOID_BUSY_NODE',
        'LCE_AVOID_BUSY_NODE',
        'LCD_AVOID_BUSY_NODE'
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
                       # 'read_delay_penalty': READ_DELAY_PENALTY,
                       # 'write_delay_penalty': WRITE_DELAY_PENALTY,
                       # 'cache_queue_size': CACHE_QUEUE_SIZE
                       }
default['cache_placement']['name'] = 'UNIFORM'
default['content_placement']['name'] = 'UNIFORM'
default['cache_policy']['name'] = CACHE_POLICY

# Set topology
default['topology']['name'] = 'TREE'
default['topology']['k'] = 4
default['topology']['h'] = 2
# default['topology']['delay'] = 1
# List of all implemented topologies
# Topology implementations are located in ./icarus/scenarios/topology.py
TOPOLOGIES = [
        'TREE'
              ]

# Create experiments multiplexing all desired parameters
for alpha in ALPHA:
    for strategy in STRATEGIES2:
        for network_cache in NETWORK_CACHE:
            # i = 0
            # while i < 5:
            experiment = copy.deepcopy(default)
            experiment['workload']['name'] = 'STATIONARY_PACKET_LEVEL_CACHE_DELAY'
            experiment['workload']['alpha'] = alpha
            # experiment['workload']['server_processing_rate'] = SERVER_PROCESSING_RATE[i]
            experiment['workload']['read_delay_penalty'] = READ_DELAY_PENALTY # [i]
            experiment['workload']['write_delay_penalty'] = WRITE_DELAY_PENALTY # [i]
            experiment['workload']['cache_queue_size'] = CACHE_QUEUE_SIZE
            experiment['strategy']['name'] = strategy
            # experiment['topology']['name'] = topology
            experiment['cache_placement']['network_cache'] = network_cache
            # i += 1
            experiment['desc'] = "Alpha: %s, strategy: %s, topology: %s, network cache: %s" \
                    % (str(alpha), strategy, TOPOLOGIES[0], str(network_cache))
            EXPERIMENT_QUEUE.append(experiment)

for alpha in ALPHA:
    for strategy in STRATEGIES1:
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















