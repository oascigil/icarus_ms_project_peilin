"""Configuration file for running a single simple simulation."""
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
N_PROCESSES = 1

# Number of times each experiment is replicated
N_REPLICATIONS = 1

# Granularity of caching.
# Currently, only OBJECT is supported
CACHING_GRANULARITY = 'OBJECT'

# Format in which results are saved.
# Result readers and writers are located in module ./icarus/results/readwrite.py
# Currently only PICKLE is supported
RESULTS_FORMAT = 'PICKLE'

# List of metrics to be measured in the experiments
# The implementation of data collectors are located in ./icarus/execution/collectors.py
DATA_COLLECTORS = ['CACHE_HIT_RATIO', 'LATENCY']

# Queue of experiments
EXPERIMENT_QUEUE = deque()

# Create experiments
default = Tree()

# Specify workload
ALPHA = [1]
default['workload'] = {'name':       'STATIONARY_PACKET_LEVEL',
                       'alpha':      ALPHA[0],
                       'n_contents': 10 ** 5,
                       'n_warmup':   10 ** 5,
                       'n_measured': 4 * 10 ** 5,
                       'rate':       1.0
                       }

# Specify cache placement
default['cache_placement']['name'] = 'UNIFORM'
NETWORK_CACHE = [0.004, 0.01, 0.05]

# Specify content placement
default['content_placement']['name'] = 'UNIFORM'

# Specify cache replacement policy
default['cache_policy']['name'] = 'LRU'

# Specify topology
default['topology']['name'] = 'PATH'
default['topology']['n'] = 10
default['topology']['delay'] = 10

# Create experiments multiplexing all desired parameters
for strategy in ['LCE_PKT_LEVEL', 'LCD_PKT_LEVEL']:
    for network_cache in NETWORK_CACHE:
        experiment = copy.deepcopy(default)
        experiment['strategy']['name'] = strategy
        experiment['cache_placement']['network_cache'] = network_cache
        experiment['desc'] = "Strategy: %s, Network_cache: %s " % (strategy, str(network_cache))
        EXPERIMENT_QUEUE.append(experiment)

