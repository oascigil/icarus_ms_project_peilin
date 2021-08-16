"""Traffic workloads

Every traffic workload to be used with Icarus must be modelled as an iterable
class, i.e. a class with at least an `__init__` method (through which it is
initialized, with values taken from the configuration file) and an `__iter__`
method that is called to return a new event.

Each call to the `__iter__` method must return a 2-tuple in which the first
element is the timestamp at which the event occurs and the second is a
dictionary, describing the event, which must contain at least the three
following attributes:
 * receiver: The name of the node issuing the request
 * content: The name of the content for which the request is issued
 * log: A boolean value indicating whether this request should be logged or not
   for measurement purposes.

Each workload must expose the `contents` attribute which is an iterable of
all content identifiers. This is needed for content placement.
"""
import random
import csv

import networkx as nx
import numpy as np

from icarus.tools import TruncatedZipfDist
from icarus.registry import register_workload

__all__ = [
        'StationaryWorkload',
        'GlobetraffWorkload',
        'TraceDrivenWorkload',
        'YCSBWorkload',
        'StationaryPacketLevelWorkload',
        'StationaryPacketLevelWorkloadWithCacheDelay'
           ]

@register_workload('STATIONARY_PACKET_LEVEL')
class StationaryPacketLevelWorkload(object):
    """This function generates events on the fly, i.e. instead of creating an
    event schedule to be kept in memory, returns an iterator that generates
    events when needed.

    This is useful for running large schedules of events where RAM is limited
    as its memory impact is considerably lower.

    These requests are Poisson-distributed while content popularity is
    Zipf-distributed

    All requests are mapped to receivers uniformly unless a positive *beta*
    parameter is specified.

    If a *beta* parameter is specified, then receivers issue requests at
    different rates. The algorithm used to determine the requests rates for
    each receiver is the following:
     * All receiver are sorted in decreasing order of degree of the PoP they
       are attached to. This assumes that all receivers have degree = 1 and are
       attached to a node with degree > 1
     * Rates are then assigned following a Zipf distribution of coefficient
       beta where nodes with higher-degree PoPs have a higher request rate

    Parameters
    ----------
    topology : fnss.Topology
        The topology to which the workload refers
    n_contents : int
        The number of content object
    alpha : float
        The Zipf alpha parameter
    beta : float, optional
        Parameter indicating
    rate : float, optional
        The mean rate of requests per second
    n_warmup : int, optional
        The number of warmup requests (i.e. requests executed to fill cache but
        not logged)
    n_measured : int, optional
        The number of logged requests after the warmup

    Returns
    -------
    events : iterator
        Iterator of events. Each event is a 2-tuple where the first element is
        the timestamp at which the event occurs and the second element is a
        dictionary of event attributes.
    """
    def __init__(self, topology, n_contents, alpha, beta=0, rate=1.0,
                    n_warmup=10 ** 5, n_measured=4 * 10 ** 5, seed=None, **kwargs):
        if alpha < 0:
            raise ValueError('alpha must be positive')
        if beta < 0:
            raise ValueError('beta must be positive')
        self.receivers = [v for v in topology.nodes()
                     if topology.node[v]['stack'][0] == 'receiver']
        self.zipf = TruncatedZipfDist(alpha, n_contents)
        self.n_contents = n_contents
        self.contents = list(range(1, n_contents + 1))
        self.alpha = alpha
        self.rate = rate
        self.n_warmup = n_warmup
        self.n_measured = n_measured
        random.seed(seed)
        self.view = None
        self.controller = None
        self.beta = beta
        # print('Stationary-pkr-level, enter init')
        if beta != 0:
            degree = nx.degree(self.topology)
            self.receivers = sorted(self.receivers, key=lambda x: degree[iter(topology.adj[x]).next()], reverse=True)
            self.receiver_dist = TruncatedZipfDist(beta, len(self.receivers))

    def __iter__(self):
        flow_counter = 0
        t_next_flow = 0.0
        # print('Stationary-pkt-level, enter iter')
        while ( (flow_counter < self.n_warmup + self.n_measured) or len(self.view.eventQ())>0 ):
            # print('Stationary-pkt-level, enter iter while')
            t_next_flow += (random.expovariate(self.rate))
            event = self.view.peek_next_event()
            # print('enter outer while, flow_counter:', flow_counter)
            while (event is not None) and (event['t_event'] < t_next_flow):
                event = self.controller.pop_next_event()
                t_event = event['t_event']
                del event['t_event']
                yield(t_event, event)
                event = self.view.peek_next_event()
                # print('flow_counter:', flow_counter, 't_event', t_event, 'event:', event)

            if flow_counter >= (self.n_warmup + self.n_measured):
                continue
            if self.beta == 0:
                receiver = random.choice(self.receivers)
            else:
                receiver = self.receivers[self.receiver_dist.rv() - 1]
            content = int(self.zipf.rv())
            if flow_counter % 1000 == 0:
                random.shuffle(self.contents)
            content = self.contents.index(content) + 1
            log = (flow_counter >= self.n_warmup)
            event = {'receiver': receiver, 'content': content, 'node': receiver, 'flow': flow_counter, 'pkt_type': 'Request', 'log': log}
            # print('flow counter: ', flow_counter, 't_next_flow', t_next_flow, 'event:', event)
            yield (t_next_flow, event)
            flow_counter += 1
        return

@register_workload('STATIONARY_PACKET_LEVEL_CACHE_DELAY')
class StationaryPacketLevelWorkloadWithCacheDelay(object):
    """This function generates events on the fly, i.e. instead of creating an
    event schedule to be kept in memory, returns an iterator that generates
    events when needed.

    This is useful for running large schedules of events where RAM is limited
    as its memory impact is considerably lower.

    These requests are Poisson-distributed while content popularity is
    Zipf-distributed

    All requests are mapped to receivers uniformly unless a positive *beta*
    parameter is specified.

    If a *beta* parameter is specified, then receivers issue requests at
    different rates. The algorithm used to determine the requests rates for
    each receiver is the following:
     * All receiver are sorted in decreasing order of degree of the PoP they
       are attached to. This assumes that all receivers have degree = 1 and are
       attached to a node with degree > 1
     * Rates are then assigned following a Zipf distribution of coefficient
       beta where nodes with higher-degree PoPs have a higher request rate

    Parameters
    ----------
    topology : fnss.Topology
        The topology to which the workload refers
    n_contents : int
        The number of content object
    alpha : float
        The Zipf alpha parameter
    beta : float, optional
        Parameter indicating
    rate : float, optional
        The mean rate of requests per second
    n_warmup : int, optional
        The number of warmup requests (i.e. requests executed to fill cache but
        not logged)
    n_measured : int, optional
        The number of logged requests after the warmup

    Returns
    -------
    events : iterator
        Iterator of events. Each event is a 2-tuple where the first element is
        the timestamp at which the event occurs and the second element is a
        dictionary of event attributes.
    """
    def __init__(self, topology, n_contents, alpha, # server_processing_rate,
                    beta=0, rate=1.0, n_warmup=10 ** 5, n_measured=4 * 10 ** 5, read_delay_penalty=100,
                    write_delay_penalty=100, cache_queue_size=10, seed=None, **kwargs):
        if alpha < 0:
            raise ValueError('alpha must be positive')
        if beta < 0:
            raise ValueError('beta must be positive')
        self.receivers = [v for v in topology.nodes()
                     if topology.node[v]['stack'][0] == 'receiver']
        self.zipf = TruncatedZipfDist(alpha, n_contents)
        self.n_contents = n_contents
        self.contents = list(range(1, n_contents + 1))
        self.alpha = alpha
        self.rate = rate
        self.n_warmup = n_warmup
        self.n_measured = n_measured
        random.seed(seed)
        self.view = None
        self.controller = None
        self.beta = beta
        self.read_delay_penalty = read_delay_penalty
        self.write_delay_penalty = write_delay_penalty
        self.cache_queue_size = cache_queue_size
        # self.server_processing_rate = server_processing_rate
        # print('Stationary-pkt-level, enter init')
        if beta != 0:
            degree = nx.degree(self.topology)
            self.receivers = sorted(self.receivers, key=lambda x: degree[iter(topology.adj[x]).next()], reverse=True)
            self.receiver_dist = TruncatedZipfDist(beta, len(self.receivers))

    def __iter__(self):
        self.controller.set_read_delay_penalty(self.read_delay_penalty)
        self.controller.set_write_delay_penalty(self.write_delay_penalty)
        self.controller.set_cache_queue_size(self.cache_queue_size)
        flow_counter = 0    
        t_next_flow = 0.0
        # print('Stationary-pkt-level, enter iter')
        while ( (flow_counter < self.n_warmup + self.n_measured) or len(self.view.eventQ())>0 ):
            # print('Stationary-pkt-level, enter iter while')
            t_next_flow += (random.expovariate(self.rate))
            # print('flow counter:', flow_counter, ', t_next_flow:', t_next_flow)
            event1 = self.view.peek_next_event()
            event2 = self.view.peek_next_cache_event()
            # print('enter outer while, flow_counter:', flow_counter)
            while ((event1 is not None) and (event1['t_event'] < t_next_flow)) \
                    or ((event2 is not None) and (event2['t_event'] < t_next_flow)):
                if ((event1 is not None) and (event1['t_event'] < t_next_flow)) \
                        and ((event2 is None) or (event2['t_event'] >= t_next_flow)):
                    event1 = self.controller.pop_next_event()
                    t_event = event1['t_event']
                    # print('event1 enabled, add event1, event1', event1, ', event2', event2)
                    del event1['t_event']
                    yield(t_event, event1)
                    event1 = self.view.peek_next_event()
                elif ((event2 is not None) and (event2['t_event'] < t_next_flow)) \
                        and ((event1 is None) or (event1['t_event'] >= t_next_flow)):
                    node = event2['node']
                    event2 = self.controller.pop_next_cache_event(node)
                    t_event = event2['t_event']
                    # self.controller.record_cache_queue_length(node, log)
                    # print('event2 enabled, add event2, event1', event1, ', event2', event2)
                    del event2['t_event']
                    yield (t_event, event2)
                    self.controller.update_cache_queue_server(node, t_event, event2)
                    event2 = self.view.peek_next_cache_event()
                else:
                    if event1['t_event'] < event2['t_event']:
                        event1 = self.controller.pop_next_event()
                        t_event = event1['t_event']
                        # print('both enabled, add event1, event1', event1, ', event2', event2)
                        del event1['t_event']
                        yield (t_event, event1)
                        event1 = self.view.peek_next_event()
                    else:
                        node = event2['node']
                        event2 = self.controller.pop_next_cache_event(node)
                        t_event = event2['t_event']
                        # self.controller.record_cache_queue_length(node, log)
                        # print('both enabled, add event2, event1', event1, ', event2', event2)
                        del event2['t_event']
                        yield (t_event, event2)
                        self.controller.update_cache_queue_server(node, t_event, event2)
                        event2 = self.view.peek_next_cache_event()
                # print('flow_counter:', flow_counter, 't_event', t_event, 'event:', event)

            if flow_counter >= (self.n_warmup + self.n_measured):
                continue
            if self.beta == 0:
                receiver = random.choice(self.receivers)
            else:
                receiver = self.receivers[self.receiver_dist.rv() - 1]
            content = int(self.zipf.rv())
            if flow_counter % 1000 == 0:
                random.shuffle(self.contents)
            content = self.contents.index(content) + 1
            log = (flow_counter >= self.n_warmup)
            event = {'receiver': receiver, 'content': content, 'node': receiver, 'flow': flow_counter, 'pkt_type': 'Request', 'log': log}
            # print('flow counter: ', flow_counter, 't_next_flow', t_next_flow, 'event:', event)
            yield (t_next_flow, event)
            flow_counter += 1
        return

@register_workload('STATIONARY')
class StationaryWorkload(object):
    """This function generates events on the fly, i.e. instead of creating an
    event schedule to be kept in memory, returns an iterator that generates
    events when needed.

    This is useful for running large schedules of events where RAM is limited
    as its memory impact is considerably lower.

    These requests are Poisson-distributed while content popularity is
    Zipf-distributed

    All requests are mapped to receivers uniformly unless a positive *beta*
    parameter is specified.

    If a *beta* parameter is specified, then receivers issue requests at
    different rates. The algorithm used to determine the requests rates for
    each receiver is the following:
     * All receiver are sorted in decreasing order of degree of the PoP they
       are attached to. This assumes that all receivers have degree = 1 and are
       attached to a node with degree > 1
     * Rates are then assigned following a Zipf distribution of coefficient
       beta where nodes with higher-degree PoPs have a higher request rate

    Parameters
    ----------
    topology : fnss.Topology
        The topology to which the workload refers
    n_contents : int
        The number of content object
    alpha : float
        The Zipf alpha parameter
    beta : float, optional
        Parameter indicating
    rate : float, optional
        The mean rate of requests per second
    n_warmup : int, optional
        The number of warmup requests (i.e. requests executed to fill cache but
        not logged)
    n_measured : int, optional
        The number of logged requests after the warmup

    Returns
    -------
    events : iterator
        Iterator of events. Each event is a 2-tuple where the first element is
        the timestamp at which the event occurs and the second element is a
        dictionary of event attributes.
    """
    def __init__(self, topology, n_contents, alpha, beta=0, rate=1.0,
                    n_warmup=10 ** 5, n_measured=4 * 10 ** 5, seed=None, **kwargs):
        # print('Stationary, enter init')
        if alpha < 0:
            raise ValueError('alpha must be positive')
        if beta < 0:
            raise ValueError('beta must be positive')
        self.receivers = [v for v in topology.nodes()
                     if topology.node[v]['stack'][0] == 'receiver']
        self.zipf = TruncatedZipfDist(alpha, n_contents)
        self.n_contents = n_contents
        self.contents = range(1, n_contents + 1)
        self.alpha = alpha
        self.rate = rate
        self.n_warmup = n_warmup
        self.n_measured = n_measured
        random.seed(seed)
        self.beta = beta
        if beta != 0:
            degree = nx.degree(self.topology)
            self.receivers = sorted(self.receivers, key=lambda x: degree[iter(topology.adj[x]).next()], reverse=True)
            self.receiver_dist = TruncatedZipfDist(beta, len(self.receivers))

    def __iter__(self):
        # print('Stationary, enter iter')
        req_counter = 0
        t_event = 0.0
        while req_counter < self.n_warmup + self.n_measured:
            # print('Stationary, enter iter while')
            t_event += (random.expovariate(self.rate))
            if self.beta == 0:
                receiver = random.choice(self.receivers)
            else:
                receiver = self.receivers[self.receiver_dist.rv() - 1]
            content = int(self.zipf.rv())
            log = (req_counter >= self.n_warmup)
            event = {'receiver': receiver, 'content': content, 'log': log}
            yield (t_event, event)
            req_counter += 1
        return


@register_workload('GLOBETRAFF')
class GlobetraffWorkload(object):
    """Parse requests from GlobeTraff workload generator

    All requests are mapped to receivers uniformly unless a positive *beta*
    parameter is specified.

    If a *beta* parameter is specified, then receivers issue requests at
    different rates. The algorithm used to determine the requests rates for
    each receiver is the following:
     * All receiver are sorted in decreasing order of degree of the PoP they
       are attached to. This assumes that all receivers have degree = 1 and are
       attached to a node with degree > 1
     * Rates are then assigned following a Zipf distribution of coefficient
       beta where nodes with higher-degree PoPs have a higher request rate

    Parameters
    ----------
    topology : fnss.Topology
        The topology to which the workload refers
    reqs_file : str
        The GlobeTraff request file
    contents_file : str
        The GlobeTraff content file
    beta : float, optional
        Spatial skewness of requests rates

    Returns
    -------
    events : iterator
        Iterator of events. Each event is a 2-tuple where the first element is
        the timestamp at which the event occurs and the second element is a
        dictionary of event attributes.
    """

    def __init__(self, topology, reqs_file, contents_file, beta=0, **kwargs):
        """Constructor"""
        if beta < 0:
            raise ValueError('beta must be positive')
        self.receivers = [v for v in topology.nodes()
                     if topology.node[v]['stack'][0] == 'receiver']
        self.n_contents = 0
        with open(contents_file, 'r') as f:
            reader = csv.reader(f, delimiter='\t')
            for content, popularity, size, app_type in reader:
                self.n_contents = max(self.n_contents, content)
        self.n_contents += 1
        self.contents = range(self.n_contents)
        self.request_file = reqs_file
        self.beta = beta
        if beta != 0:
            degree = nx.degree(self.topology)
            self.receivers = sorted(self.receivers, key=lambda x:
                                    degree[iter(topology.adj[x]).next()],
                                    reverse=True)
            self.receiver_dist = TruncatedZipfDist(beta, len(self.receivers))

    def __iter__(self):
        with open(self.request_file, 'r') as f:
            reader = csv.reader(f, delimiter='\t')
            for timestamp, content, size in reader:
                if self.beta == 0:
                    receiver = random.choice(self.receivers)
                else:
                    receiver = self.receivers[self.receiver_dist.rv() - 1]
                event = {'receiver': receiver, 'content': content, 'size': size}
                yield (timestamp, event)
        return


@register_workload('TRACE_DRIVEN')
class TraceDrivenWorkload(object):
    """Parse requests from a generic request trace.

    This workload requires two text files:
     * a requests file, where each line corresponds to a string identifying
       the content requested
     * a contents file, which lists all unique content identifiers appearing
       in the requests file.

    Since the trace do not provide timestamps, requests are scheduled according
    to a Poisson process of rate *rate*. All requests are mapped to receivers
    uniformly unless a positive *beta* parameter is specified.

    If a *beta* parameter is specified, then receivers issue requests at
    different rates. The algorithm used to determine the requests rates for
    each receiver is the following:
     * All receiver are sorted in decreasing order of degree of the PoP they
       are attached to. This assumes that all receivers have degree = 1 and are
       attached to a node with degree > 1
     * Rates are then assigned following a Zipf distribution of coefficient
       beta where nodes with higher-degree PoPs have a higher request rate

    Parameters
    ----------
    topology : fnss.Topology
        The topology to which the workload refers
    reqs_file : str
        The path to the requests file
    contents_file : str
        The path to the contents file
    n_contents : int
        The number of content object (i.e. the number of lines of contents_file)
    n_warmup : int
        The number of warmup requests (i.e. requests executed to fill cache but
        not logged)
    n_measured : int
        The number of logged requests after the warmup
    rate : float, optional
        The network-wide mean rate of requests per second
    beta : float, optional
        Spatial skewness of requests rates

    Returns
    -------
    events : iterator
        Iterator of events. Each event is a 2-tuple where the first element is
        the timestamp at which the event occurs and the second element is a
        dictionary of event attributes.
    """

    def __init__(self, topology, reqs_file, contents_file, n_contents,
                 n_warmup, n_measured, rate=1.0, beta=0, **kwargs):
        """Constructor"""
        if beta < 0:
            raise ValueError('beta must be positive')
        # Set high buffering to avoid one-line reads
        self.buffering = 64 * 1024 * 1024
        self.n_contents = n_contents
        self.n_warmup = n_warmup
        self.n_measured = n_measured
        self.reqs_file = reqs_file
        self.rate = rate
        self.receivers = [v for v in topology.nodes()
                          if topology.node[v]['stack'][0] == 'receiver']
        self.contents = []
        with open(contents_file, 'r', buffering=self.buffering) as f:
            for content in f:
                self.contents.append(content)
        self.beta = beta
        if beta != 0:
            degree = nx.degree(topology)
            self.receivers = sorted(self.receivers, key=lambda x:
                                    degree[iter(topology.adj[x]).next()],
                                    reverse=True)
            self.receiver_dist = TruncatedZipfDist(beta, len(self.receivers))

    def __iter__(self):
        req_counter = 0
        t_event = 0.0
        with open(self.reqs_file, 'r', buffering=self.buffering) as f:
            for content in f:
                t_event += (random.expovariate(self.rate))
                if self.beta == 0:
                    receiver = random.choice(self.receivers)
                else:
                    receiver = self.receivers[self.receiver_dist.rv() - 1]
                log = (req_counter >= self.n_warmup)
                event = {'receiver': receiver, 'content': content, 'log': log}
                yield (t_event, event)
                req_counter += 1
                if(req_counter >= self.n_warmup + self.n_measured):
                    return
            raise ValueError("Trace did not contain enough requests")


@register_workload('YCSB')
class YCSBWorkload(object):
    """Yahoo! Cloud Serving Benchmark (YCSB)

    The YCSB is a set of reference workloads used to benchmark databases and,
    more generally any storage/caching systems. It comprises five workloads:

    +------------------+------------------------+------------------+
    | Workload         | Operations             | Record selection |
    +------------------+------------------------+------------------+
    | A - Update heavy | Read: 50%, Update: 50% | Zipfian          |
    | B - Read heavy   | Read: 95%, Update: 5%  | Zipfian          |
    | C - Read only    | Read: 100%             | Zipfian          |
    | D - Read latest  | Read: 95%, Insert: 5%  | Latest           |
    | E - Short ranges | Scan: 95%, Insert 5%   | Zipfian/Uniform  |
    +------------------+------------------------+------------------+

    Notes
    -----
    At the moment only workloads A, B and C are implemented, since they are the
    most relevant for caching systems.
    """

    def __init__(self, workload, n_contents, n_warmup, n_measured, alpha=0.99, seed=None, **kwargs):
        """Constructor

        Parameters
        ----------
        workload : str
            Workload identifier. Currently supported: "A", "B", "C"
        n_contents : int
            Number of content items
        n_warmup : int, optional
            The number of warmup requests (i.e. requests executed to fill cache but
            not logged)
        n_measured : int, optional
            The number of logged requests after the warmup
        alpha : float, optional
            Parameter of Zipf distribution
        seed : int, optional
            The seed for the random generator
        """

        if workload not in ("A", "B", "C", "D", "E"):
            raise ValueError("Incorrect workload ID [A-B-C-D-E]")
        elif workload in ("D", "E"):
            raise NotImplementedError("Workloads D and E not yet implemented")
        self.workload = workload
        if seed is not None:
            random.seed(seed)
        self.zipf = TruncatedZipfDist(alpha, n_contents)
        self.n_warmup = n_warmup
        self.n_measured = n_measured

    def __iter__(self):
        """Return an iterator over the workload"""
        req_counter = 0
        while req_counter < self.n_warmup + self.n_measured:
            rand = random.random()
            op = {
                  "A": "READ" if rand < 0.5 else "UPDATE",
                  "B": "READ" if rand < 0.95 else "UPDATE",
                  "C": "READ"
                  }[self.workload]
            item = int(self.zipf.rv())
            log = (req_counter >= self.n_warmup)
            event = {'op': op, 'item': item, 'log': log}
            yield event
            req_counter += 1
        return
