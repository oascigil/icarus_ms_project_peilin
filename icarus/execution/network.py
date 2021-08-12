"""Network Model-View-Controller (MVC)

This module contains classes providing an abstraction of the network shown to
the strategy implementation. The network is modelled using an MVC design
pattern.

A strategy performs actions on the network by calling methods of the
`NetworkController`, that in turns updates  the `NetworkModel` instance that
updates the `NetworkView` instance. The strategy can get updated information
about the network status by calling methods of the `NetworkView` instance.

The `NetworkController` is also responsible to notify a `DataCollectorProxy`
of all relevant events.
"""
import logging

import networkx as nx
import fnss
import math
import heapq

from icarus.registry import CACHE_POLICY
from icarus.util import iround, path_links

__all__ = [
    'NetworkModel',
    'NetworkView',
    'NetworkController'
          ]

logger = logging.getLogger('orchestration')


def symmetrify_paths(shortest_paths):
    """Make paths symmetric

    Given a dictionary of all-pair shortest paths, it edits shortest paths to
    ensure that all path are symmetric, e.g., path(u,v) = path(v,u)

    Parameters
    ----------
    shortest_paths : dict of dict
        All pairs shortest paths

    Returns
    -------
    shortest_paths : dict of dict
        All pairs shortest paths, with all paths symmetric

    Notes
    -----
    This function modifies the shortest paths dictionary provided
    """
    for u in shortest_paths:
        for v in shortest_paths[u]:
            shortest_paths[u][v] = list(reversed(shortest_paths[v][u]))
    return shortest_paths


class NetworkView(object):
    """Network view

    This class provides an interface that strategies and data collectors can
    use to know updated information about the status of the network.
    For example the network view provides information about shortest paths,
    characteristics of links and currently cached objects in nodes.
    """

    def __init__(self, model):
        """Constructor

        Parameters
        ----------
        model : NetworkModel
            The network model instance
        """
        if not isinstance(model, NetworkModel):
            raise ValueError('The model argument must be an instance of '
                             'NetworkModel')
        self.model = model

    def content_locations(self, k):
        """Return a set of all current locations of a specific content.

        This include both persistent content sources and temporary caches.

        Parameters
        ----------
        k : any hashable type
            The content identifier

        Returns
        -------
        nodes : set
            A set of all nodes currently storing the given content
        """
        loc = set(v for v in self.model.cache if self.model.cache[v].has(k))
        source = self.content_source(k)
        if source:
            loc.add(source)
        return loc

    def content_source(self, k):
        """Return the node identifier where the content is persistently stored.

        Parameters
        ----------
        k : any hashable type
            The content identifier

        Returns
        -------
        node : any hashable type
            The node persistently storing the given content or None if the
            source is unavailable
        """
        return self.model.content_source.get(k, None)

    def shortest_path(self, s, t):
        """Return the shortest path from *s* to *t*

        Parameters
        ----------
        s : any hashable type
            Origin node
        t : any hashable type
            Destination node

        Returns
        -------
        shortest_path : list
            List of nodes of the shortest path (origin and destination
            included)
        """
        # print('shortest path', s, t)
        return self.model.shortest_path[s][t]

    def all_pairs_shortest_paths(self):
        """Return all pairs shortest paths

        Return
        ------
        all_pairs_shortest_paths : dict of lists
            Shortest paths between all pairs
        """
        return self.model.shortest_path

    def peek_next_event(self):
        """Return the next (soonest) event in the eventQ without removing the 
           event from the eventQ
        """
        return self.model.eventQ[0][1] if len(self.model.eventQ) > 0 else None
        # return self.model.eventQ[0] if len(self.model.eventQ) > 0 else None

    def eventQ(self):
        """Return the eventQ
        """
        return self.model.eventQ

    # put the first cache event of each router in a single queue
    # and sort according to time, return the first event
    def peek_next_cache_event(self):
        """put the first cache event of each router in a single queue and sort according to time,
           return the first event in the new queue without removing the event from the cacheQ
        """
        queue = []
        heapq.heapify(queue)
        for node in self.model.cacheQ:
            events = self.model.cacheQ[node]
            if events != []:
                heapq.heappush(queue, events[0])

        if queue != []:
            next_event = queue[0]
            return next_event[1]
        else:
            return None
            # queue.append(events[0]) if (events != []) else None
            # queue.sort(key=lambda i: i['t_event'])
        # return queue[0] if (queue != []) else None

    def cacheQ(self):
        """Return the cacheQ
        """
        return self.model.cacheQ

    def cacheQ_node(self, node):
        """Return the cacheQ in a node
        """
        if node in self.model.cacheQ:
            return self.model.cacheQ[node]
        else:
            return []

    def cacheQ_server(self, node):
        """Return the event in the server
        """
        if node in self.model.server:
            return self.model.server[node]
        else:
            return None

    # get read operations delay penalty
    def get_read_delay_penalty(self):
        return self.model.read_delay_penalty

    # get write operations delay penalty
    def get_write_delay_penalty(self):
        return self.model.write_delay_penalty

    # get cache queue size
    def get_cache_queue_size(self):
        return self.model.cacheQ_size

    # get cache queue delay
    def get_cache_queue_delay(self, node, time):
        read_delay_penalty = self.model.read_delay_penalty
        write_delay_penalty = self.model.write_delay_penalty
        server = self.cacheQ_server(node)
        cacheQ = self.cacheQ_node(node)
        delay = 0
        if server == None and cacheQ == []:
            delay = 0
            queue_delay = delay
        elif server == None and cacheQ != []:
            for event in cacheQ:
                event = event[1]
                if event['pkt_type'] == 'get_content':
                    delay += read_delay_penalty
                elif event['pkt_type'] == 'put_content:':
                    delay += write_delay_penalty
            queue_delay = delay
        elif server != None and cacheQ == []:
            # server delay
            if server['pkt_type'] == 'get_content':
                delay += read_delay_penalty
            elif server['pkt_type'] == 'put_content:':
                delay += write_delay_penalty
            queue_delay = math.ceil(server['t_event'] + delay - time)
        else:
            if server['pkt_type'] == 'get_content':
                delay += read_delay_penalty
            elif server['pkt_type'] == 'put_content':
                delay += write_delay_penalty
            for event in cacheQ:
                event = event[1]
                if event['pkt_type'] == 'get_content':
                    delay += read_delay_penalty
                elif event['pkt_type'] == 'put_content':
                    delay += write_delay_penalty
            queue_delay = math.ceil(server['t_event'] + delay - time)
        if queue_delay < 0:
            queue_delay = 0
        return queue_delay


    def cluster(self, v):
        """Return cluster to which a node belongs, if any

        Parameters
        ----------
        v : any hashable type
            Node

        Returns
        -------
        cluster : int
            Cluster to which the node belongs, None if the topology is not
            clustered or the node does not belong to any cluster
        """
        if 'cluster' in self.model.topology.node[v]:
            return self.model.topology.node[v]['cluster']
        else:
            return None

    def link_type(self, u, v):
        """Return the type of link *(u, v)*.

        Type can be either *internal* or *external*

        Parameters
        ----------
        u : any hashable type
            Origin node
        v : any hashable type
            Destination node

        Returns
        -------
        link_type : str
            The link type
        """
        return self.model.link_type[(u, v)]

    def link_delay(self, u, v):
        """Return the delay of link *(u, v)*.

        Parameters
        ----------
        u : any hashable type
            Origin node
        v : any hashable type
            Destination node

        Returns
        -------
        delay : float
            The link delay
        """
        return self.model.link_delay[(u, v)]

    def topology(self):
        """Return the network topology

        Returns
        -------
        topology : fnss.Topology
            The topology object

        Notes
        -----
        The topology object returned by this method must not be modified by the
        caller. This object can only be modified through the NetworkController.
        Changes to this object will lead to inconsistent network state.
        """
        return self.model.topology

    def cache_nodes(self, size=False):
        """Returns a list of nodes with caching capability

        Parameters
        ----------
        size: bool, opt
            If *True* return dict mapping nodes with size

        Returns
        -------
        cache_nodes : list or dict
            If size parameter is False or not specified, it is a list of nodes
            with caches. Otherwise it is a dict mapping nodes with a cache
            and their size.
        """
        return {v: c.maxlen for v, c in self.model.cache.items()} if size \
                else list(self.model.cache.keys())

    def has_cache(self, node):
        """Check if a node has a content cache.

        Parameters
        ----------
        node : any hashable type
            The node identifier

        Returns
        -------
        has_cache : bool,
            *True* if the node has a cache, *False* otherwise
        """
        return node in self.model.cache

    def cache_lookup(self, node, content):
        """Check if the cache of a node has a content object, without changing
        the internal state of the cache.

        This method is meant to be used by data collectors to calculate
        metrics. It should not be used by strategies to look up for contents
        during the simulation. Instead they should use
        `NetworkController.get_content`

        Parameters
        ----------
        node : any hashable type
            The node identifier
        content : any hashable type
            The content identifier

        Returns
        -------
        has_content : bool
            *True* if the cache of the node has the content, *False* otherwise.
            If the node does not have a cache, return *None*
        """
        if node in self.model.cache:
            return self.model.cache[node].has(content)

    def local_cache_lookup(self, node, content):
        """Check if the local cache of a node has a content object, without
        changing the internal state of the cache.

        The local cache is an area of the cache of a node reserved for
        uncoordinated caching. This is currently used only by hybrid
        hash-routing strategies.

        This method is meant to be used by data collectors to calculate
        metrics. It should not be used by strategies to look up for contents
        during the simulation. Instead they should use
        `NetworkController.get_content_local_cache`.

        Parameters
        ----------
        node : any hashable type
            The node identifier
        content : any hashable type
            The content identifier

        Returns
        -------
        has_content : bool
            *True* if the cache of the node has the content, *False* otherwise.
            If the node does not have a cache, return *None*
        """
        if node in self.model.local_cache:
            return self.model.local_cache[node].has(content)
        else:
            return False

    def cache_dump(self, node):
        """Returns the dump of the content of a cache in a specific node

        Parameters
        ----------
        node : any hashable type
            The node identifier

        Returns
        -------
        dump : list
            List of contents currently in the cache
        """
        if node in self.model.cache:
            return self.model.cache[node].dump()

    # get LCD status
    def get_lcd_flow_copied_flag(self, flow):
        """Return the flag indicating copied or not in LCD

        Parameters
        ----------
        flag : True for already copied
               False for not copied yet
        """
        return self.model.lcd_pkt_level_copied_flag[flow]

    # get ProbCache status
    def get_probcache_c(self, flow):
        """Return the flag indicating copied or not in LCD

        Parameters
        ----------
        flag : True for already copied
               False for not copied yet
        """
        return self.model.ProbCache_c[flow]

    def get_probcache_N(self, flow):
        """Return the flag indicating copied or not in LCD

        Parameters
        ----------
        flag : True for already copied
               False for not copied yet
        """
        return self.model.ProbCache_N[flow]

    def get_probcache_x(self, flow):
        """Return the flag indicating copied or not in LCD

        Parameters
        ----------
        flag : True for already copied
               False for not copied yet
        """
        return self.model.ProbCache_x[flow]


class NetworkModel(object):
    """Models the internal state of the network.

    This object should never be edited by strategies directly, but only through
    calls to the network controller.
    """

    def __init__(self, topology, cache_policy, shortest_path=None):
        """Constructor

        Parameters
        ----------
        topology : fnss.Topology
            The topology object
        cache_policy : dict or Tree
            cache policy descriptor. It has the name attribute which identify
            the cache policy name and keyworded arguments specific to the
            policy
        shortest_path : dict of dict, optional
            The all-pair shortest paths of the network
        """


        # Filter inputs
        if not isinstance(topology, fnss.Topology):
            raise ValueError('The topology argument must be an instance of '
                             'fnss.Topology or any of its subclasses.')

        # Shortest paths of the network
        self.shortest_path = dict(shortest_path) if shortest_path is not None \
                             else symmetrify_paths(dict(nx.all_pairs_dijkstra_path(topology)))

        # Network topology
        self.topology = topology

        # Dictionary mapping each content object to its source
        # dict of location of contents keyed by content ID
        self.content_source = {}
        # Dictionary mapping the reverse, i.e. nodes to set of contents stored
        self.source_node = {}

        # Dictionary of link types (internal/external)
        self.link_type = nx.get_edge_attributes(topology, 'type')
        self.link_delay = fnss.get_delays(topology)
        # [Instead of this manual assignment, I could have converted the
        # topology to directed before extracting type and link delay but that
        # requires a deep copy of the topology that can take long time if
        # many content source mappings are included in the topology
        if not topology.is_directed():
            for (u, v), link_type in list(self.link_type.items()):
                self.link_type[(v, u)] = link_type
            for (u, v), delay in list(self.link_delay.items()):
                self.link_delay[(v, u)] = delay

        cache_size = {}
        for node in topology.nodes():
            stack_name, stack_props = fnss.get_stack(topology, node)
            if stack_name == 'router':
                if 'cache_size' in stack_props:
                    cache_size[node] = stack_props['cache_size']
            elif stack_name == 'source':
                contents = stack_props['contents']
                self.source_node[node] = contents
                for content in contents:
                    self.content_source[content] = node
        if any(c < 1 for c in cache_size.values()):
            logger.warn('Some content caches have size equal to 0. '
                        'I am setting them to 1 and run the experiment anyway')
            for node in cache_size:
                if cache_size[node] < 1:
                    cache_size[node] = 1

        policy_name = cache_policy['name']
        policy_args = {k: v for k, v in cache_policy.items() if k != 'name'}
        # The actual cache objects storing the content
        self.cache = {node: CACHE_POLICY[policy_name](cache_size[node], **policy_args)
                          for node in cache_size}

        # This is for a local un-coordinated cache (currently used only by
        # Hashrouting with edge cache)
        self.local_cache = {}

        # Keep track of nodes and links removed to simulate failures
        self.removed_nodes = {}
        # This keeps track of neighbors of a removed node at the time of removal.
        # It is needed to ensure that when the node is restored only links that
        # were removed as part of the node removal are restored and to prevent
        # restoring nodes that were removed manually before removing the node.
        self.disconnected_neighbors = {}
        self.removed_links = {}
        self.removed_sources = {}
        self.removed_caches = {}
        self.removed_local_caches = {}

        # A priority queue of events
        self.eventQ = []
        heapq.heapify(self.eventQ)

        #  A priority queue of cache read/write events
        self.cacheQ = {}
        self.server = {}
        # self.cacheQ_length = [[],[]]
        self.read_delay_penalty = 100
        self.write_delay_penalty = 100
        self.cacheQ_size = 10

        # LCD packet level flag indicating content copied or not
        self.lcd_pkt_level_copied_flag = {}

        # ProbCache parameters
        # c: the number of nodes that has cache when returning content
        self.ProbCache_c = {}
        # N: the sum of cache sizes of nodes when returning content
        self.ProbCache_N = {}
        # x: the number of nodes that in cache_size
        self.ProbCache_x = {}



class NetworkController(object):
    """Network controller

    This class is in charge of executing operations on the network model on
    behalf of a strategy implementation. It is also in charge of notifying
    data collectors of relevant events.
    """

    def __init__(self, model):
        """Constructor

        Parameters
        ----------
        model : NetworkModel
            Instance of the network model
        """
        self.session = None
        self.model = model
        self.collector = None

    def add_event(self, event):
        """ Add an event to the eventQ
        Parameters
        ----------
        event : a new event
            a dict
        """
        # self.model.eventQ.insert(0,event)
        ## Sort events in the eventQ by "time of event" (t_event)
        ## self.model.eventQ = sorted(self.model.eventQ, key = lambda i: i['t_event'])
        # self.model.eventQ.sort(key=lambda i:i['t_event'])
        # print('add event:', event)
        heapq.heappush(self.model.eventQ, (event['t_event'], event))

    def pop_next_event(self):
        """
        Remove the first (soonest) event from the eventQ
        """
        # print('soonest event', self.model.eventQ[0])
        event = heapq.heappop(self.model.eventQ)
        return event[1]
        # event = self.model.eventQ.pop(0)
        # return event

    def attach_collector(self, collector):
        """Attach a data collector to which all events will be reported.

        Parameters
        ----------
        collector : DataCollector
            The data collector
        """
        self.collector = collector

    def detach_collector(self):
        """Detach the data collector."""
        self.collector = None

    def start_session(self, timestamp, receiver, content, log):
        """Instruct the controller to start a new session (i.e. the retrieval
        of a content).

        Parameters
        ----------
        timestamp : int
            The timestamp of the event
        receiver : any hashable type
            The receiver node requesting a content
        content : any hashable type
            The content identifier requested by the receiver
        log : bool
            *True* if this session needs to be reported to the collector,
            *False* otherwise
        """
        self.session = dict(timestamp=timestamp,
                            receiver=receiver,
                            content=content,
                            log=log)
        if self.collector is not None and self.session['log']:
            self.collector.start_session(timestamp, receiver, content)

    def start_flow_session(self, timestamp, receiver, content, flow, log):
        """Instruct the controller to start a new session (i.e. the retrieval
        of a content).

        Parameters
        ----------
        timestamp : int
            The timestamp of the event
        receiver : any hashable type
            The receiver node requesting a content
        content : any hashable type
            The content identifier requested by the receiver
        log : bool
            *True* if this session needs to be reported to the collector,
            *False* otherwise
        """
        if self.collector is not None and log:
            self.collector.start_flow_session(timestamp, receiver, content, flow)

    def forward_request_path(self, s, t, path=None, main_path=True):
        """Forward a request from node *s* to node *t* over the provided path.

        Parameters
        ----------
        s : any hashable type
            Origin node
        t : any hashable type
            Destination node
        path : list, optional
            The path to use. If not provided, shortest path is used
        main_path : bool, optional
            If *True*, indicates that link path is on the main path that will
            lead to hit a content. It is normally used to calculate latency
            correctly in multicast cases. Default value is *True*
        """
        if path is None:
            path = self.model.shortest_path[s][t]
        for u, v in path_links(path):
            self.forward_request_hop(u, v, main_path)

    def forward_content_path(self, u, v, path=None, main_path=True):
        """Forward a content from node *s* to node *t* over the provided path.

        Parameters
        ----------
        s : any hashable type
            Origin node
        t : any hashable type
            Destination node
        path : list, optional
            The path to use. If not provided, shortest path is used
        main_path : bool, optional
            If *True*, indicates that this path is being traversed by content
            that will be delivered to the receiver. This is needed to
            calculate latency correctly in multicast cases. Default value is
            *True*
        """
        if path is None:
            path = self.model.shortest_path[u][v]
        for u, v in path_links(path):
            self.forward_content_hop(u, v, main_path)

    def forward_request_hop_flow(self, u, v, flow, log, main_path=True):
        """Forward a request over link  u -> v.

        Parameters
        ----------
        u : any hashable type
            Origin node
        v : any hashable type
            Destination node
        main_path : bool, optional
            If *True*, indicates that link link is on the main path that will
            lead to hit a content. It is normally used to calculate latency
            correctly in multicast cases. Default value is *True*
        """
        if self.collector is not None and log:
            self.collector.request_hop_flow(u, v, flow, main_path)

    def forward_request_hop(self, u, v, main_path=True):
        """Forward a request over link  u -> v.

        Parameters
        ----------
        u : any hashable type
            Origin node
        v : any hashable type
            Destination node
        main_path : bool, optional
            If *True*, indicates that link link is on the main path that will
            lead to hit a content. It is normally used to calculate latency
            correctly in multicast cases. Default value is *True*
        """
        if self.collector is not None and self.session['log']:
            self.collector.request_hop(u, v, main_path)

    def forward_content_hop_flow(self, u, v, flow, log, main_path=True):
        """Forward a content over link  u -> v.

        Parameters
        ----------
        u : any hashable type
            Origin node
        v : any hashable type
            Destination node
        main_path : bool, optional
            If *True*, indicates that this link is being traversed by content
            that will be delivered to the receiver. This is needed to
            calculate latency correctly in multicast cases. Default value is
            *True*
        """
        if self.collector is not None and log:
            self.collector.content_hop_flow(u, v, flow, main_path)

    def forward_content_hop(self, u, v, main_path=True):
        """Forward a content over link  u -> v.

        Parameters
        ----------
        u : any hashable type
            Origin node
        v : any hashable type
            Destination node
        main_path : bool, optional
            If *True*, indicates that this link is being traversed by content
            that will be delivered to the receiver. This is needed to
            calculate latency correctly in multicast cases. Default value is
            *True*
        """
        if self.collector is not None and self.session['log']:
            self.collector.content_hop(u, v, main_path)

    def put_content_flow(self, node, content, flow):
        """Store content in the specified node.

        The node must have a cache stack and the actual insertion of the
        content is executed according to the caching policy. If the caching
        policy has a selective insertion policy, then content may not be
        inserted.

        Parameters
        ----------
        node : any hashable type
            The node where the content is inserted

        Returns
        -------
        evicted : any hashable type
            The evicted object or *None* if no contents were evicted.
        """
        if node in self.model.cache:
            return self.model.cache[node].put(content)

    def put_content(self, node, content=None):
        """Store content in the specified node.

        The node must have a cache stack and the actual insertion of the
        content is executed according to the caching policy. If the caching
        policy has a selective insertion policy, then content may not be
        inserted.

        Parameters
        ----------
        node : any hashable type
            The node where the content is inserted

        Returns
        -------
        evicted : any hashable type
            The evicted object or *None* if no contents were evicted.
        """
        if content is None:
            if node in self.model.cache:
                return self.model.cache[node].put(self.session['content'])
        else:
            if node in self.model.cache:
                return self.model.cache[node].put(content)

    def get_content(self, node):
        """Get a content from a server or a cache.

        Parameters
        ----------
        node : any hashable type
            The node where the content is retrieved

        Returns
        -------
        content : bool
            True if the content is available, False otherwise
        """
        if node in self.model.cache:
            cache_hit = self.model.cache[node].get(self.session['content'])
            if cache_hit:
                if self.session['log']:
                    self.collector.cache_hit(node)
            else:
                if self.session['log']:
                    self.collector.cache_miss(node)
            return cache_hit
        name, props = fnss.get_stack(self.model.topology, node)
        if name == 'source' and self.session['content'] in props['contents']:
            if self.collector is not None and self.session['log']:
                self.collector.server_hit(node)
            return True
        else:
            return False

    def get_content_flow(self, node, content, flow, log):
        """Get a content from a server or a cache.

        Parameters
        ----------
        node : any hashable type
            The node where the content is retrieved

        Returns
        -------
        content : bool
            True if the content is available, False otherwise
        """
        if node in self.model.cache:
            cache_hit = self.model.cache[node].get(content)
            if cache_hit:
                if log:
                    self.collector.cache_hit_flow(node, content, flow)
            else:
                if log:
                    self.collector.cache_miss_flow(node, content, flow)
            return cache_hit
        name, props = fnss.get_stack(self.model.topology, node)
        if name == 'source' and content in props['contents']:
            if self.collector is not None and log:
                self.collector.server_hit_flow(node, content, flow)
            return True
        else:
            return False

    # add delay penalty of cache operations
    def add_cache_queue_event(self, node, event):
        """ Add an event to the eventQ
        Parameters
        ----------

        node : the node
        event : a new event
            a dict
        """
        # print('enter add cache queue event, node:', node, ', event:', event)
        if node not in self.model.cacheQ:
            self.model.cacheQ[node] = []
            heapq.heapify(self.model.cacheQ[node])
        heapq.heappush(self.model.cacheQ[node], (event['t_event'], event))
        # self.model.cacheQ[node].insert(0,event)
        ## Sort events in the eventQ by "time of event" (t_event)
        ## self.model.eventQ = sorted(self.model.eventQ, key = lambda i: i['t_event'])
        # self.model.cacheQ[node].sort(key=lambda i:i['t_event'])

    def pop_next_cache_event(self, node):
        """
        Remove the first (soonest) event from the eventQ
        """
        event = heapq.heappop(self.model.cacheQ[node])
        return event[1]
        # event = self.model.cacheQ[node].pop(0)
        # return event

    # add delay penalty of cache operations
    def update_cache_queue_server(self, node, t_event, event):
        """ Push an event to the eventQ server.
        Single server.
        Parameters
        ----------

        node : the node
        event : a new event
            a dict
        """
        event['t_event'] = t_event
        self.model.server[node] = event
        # self.model.cacheQ[node].insert(0,event)
        ## Sort events in the eventQ by "time of event" (t_event)
        ## self.model.eventQ = sorted(self.model.eventQ, key = lambda i: i['t_event'])
        # self.model.cacheQ[node].sort(key=lambda i:i['t_event'])

    def pop_cache_queue_server(self, node):
        """
        Remove the first (soonest) event from the eventQ
        """
        event = self.model.server[node].pop(0)
        return event

    def record_cache_queue_length(self, log, main_path=True):
       """Record the cache queue length of a node.
       """
       if self.collector is not None and log:
           self.collector.record_cache_queue_length(main_path)

    def record_pkt_rejected(self, node, pkt_type, log, main_path=True):
       """Rrecord the number of rejected request/data.
       """
       if self.collector is not None and log:
           self.collector.record_pkt_rejected(node, pkt_type, main_path)

    def record_pkt_admitted(self, node, pkt_type, log, main_path=True):
       """record the number of admitted request/data.
       """
       if self.collector is not None and log:
           self.collector.record_pkt_admitted(node, pkt_type, main_path)

    def report_cache_queue_size(self, node, pkt_type, log, main_path=True):
       """Report cache queue size when admit a request/data.
       """
       if self.collector is not None and log:
           self.collector.report_cache_queue_size(node, pkt_type, main_path)

    def cache_operation_flow(self, flow, delay, log, main_path=True):
        """Write a content to cache or read a content from cache.

        Parameters
        ----------
        main_path : bool, optional
            If *True*, indicates that this link is being traversed by content
            that will be delivered to the receiver. This is needed to
            calculate latency correctly in multicast cases. Default value is
            *True*
        """
        # print('cache_operation_flow')
        if self.collector is not None and log:
            self.collector.cache_operation_flow(flow, delay, main_path)

    # set cache operations delay penalty
    def set_read_delay_penalty(self, delay):
        self.model.read_delay_penalty = delay

    # set cache operations delay penalty
    def set_write_delay_penalty(self, delay):
        self.model.write_delay_penalty = delay

    # set cache size
    def set_cache_queue_size(self, size=10**2):
        self.model.cacheQ_size = size


    def remove_content(self, node):
        """Remove the content being handled from the cache

        Parameters
        ----------
        node : any hashable type
            The node where the cached content is removed

        Returns
        -------
        removed : bool
            *True* if the entry was in the cache, *False* if it was not.
        """
        if node in self.model.cache:
            return self.model.cache[node].remove(self.session['content'])

    def end_flow_session(self, flow, log, success=True):
        """Close a session

        Parameters
        ----------
        success : bool, optional
            *True* if the session was completed successfully, *False* otherwise
        """
        if self.collector is not None and log:
            self.collector.end_flow_session(flow, success)

    def end_flow_session_cache_delay(self, flow, log, success=True):
        """Close a session

        Parameters
        ----------
        success : bool, optional
            *True* if the session was completed successfully, *False* otherwise
        """
        if self.collector is not None and log:
            self.collector.end_flow_session_cache_delay(flow, success)


    def end_session(self, success=True):
        """Close a session

        Parameters
        ----------
        success : bool, optional
            *True* if the session was completed successfully, *False* otherwise
        """
        if self.collector is not None and self.session['log']:
            self.collector.end_session(success)
        self.session = None

    def rewire_link(self, u, v, up, vp, recompute_paths=True):
        """Rewire an existing link to new endpoints

        This method can be used to model mobility patters, e.g., changing
        attachment points of sources and/or receivers.

        Note well. With great power comes great responsibility. Be careful when
        using this method. In fact as a result of link rewiring, network
        partitions and other corner cases might occur. Ensure that the
        implementation of strategies using this method deal with all potential
        corner cases appropriately.

        Parameters
        ----------
        u, v : any hashable type
            Endpoints of link before rewiring
        up, vp : any hashable type
            Endpoints of link after rewiring
        """
        link = self.model.topology.adj[u][v]
        self.model.topology.remove_edge(u, v)
        self.model.topology.add_edge(up, vp, **link)
        if recompute_paths:
            shortest_path = dict(nx.all_pairs_dijkstra_path(self.model.topology))
            self.model.shortest_path = symmetrify_paths(shortest_path)

    def remove_link(self, u, v, recompute_paths=True):
        """Remove a link from the topology and update the network model.

        Note well. With great power comes great responsibility. Be careful when
        using this method. In fact as a result of link removal, network
        partitions and other corner cases might occur. Ensure that the
        implementation of strategies using this method deal with all potential
        corner cases appropriately.

        Also, note that, for these changes to be effective, the strategy must
        use fresh data provided by the network view and not storing local copies
        of network state because they won't be updated by this method.

        Parameters
        ----------
        u : any hashable type
            Origin node
        v : any hashable type
            Destination node
        recompute_paths: bool, optional
            If True, recompute all shortest paths
        """
        self.model.removed_links[(u, v)] = self.model.topology.adj[u][v]
        self.model.topology.remove_edge(u, v)
        if recompute_paths:
            shortest_path = dict(nx.all_pairs_dijkstra_path(self.model.topology))
            self.model.shortest_path = symmetrify_paths(shortest_path)

    def restore_link(self, u, v, recompute_paths=True):
        """Restore a previously-removed link and update the network model

        Parameters
        ----------
        u : any hashable type
            Origin node
        v : any hashable type
            Destination node
        recompute_paths: bool, optional
            If True, recompute all shortest paths
        """
        self.model.topology.add_edge(u, v, **self.model.removed_links.pop((u, v)))
        if recompute_paths:
            shortest_path = dict(nx.all_pairs_dijkstra_path(self.model.topology))
            self.model.shortest_path = symmetrify_paths(shortest_path)

    def remove_node(self, v, recompute_paths=True):
        """Remove a node from the topology and update the network model.

        Note well. With great power comes great responsibility. Be careful when
        using this method. In fact, as a result of node removal, network
        partitions and other corner cases might occur. Ensure that the
        implementation of strategies using this method deal with all potential
        corner cases appropriately.

        It should be noted that when this method is called, all links connected
        to the node to be removed are removed as well. These links are however
        restored when the node is restored. However, if a link attached to this
        node was previously removed using the remove_link method, restoring the
        node won't restore that link as well. It will need to be restored with a
        call to restore_link.

        This method is normally quite safe when applied to remove cache nodes or
        routers if this does not cause partitions. If used to remove content
        sources or receiver, special attention is required. In particular, if
        a source is removed, the content items stored by that source will no
        longer be available if not cached elsewhere.

        Also, note that, for these changes to be effective, the strategy must
        use fresh data provided by the network view and not storing local copies
        of network state because they won't be updated by this method.

        Parameters
        ----------
        v : any hashable type
            Node to remove
        recompute_paths: bool, optional
            If True, recompute all shortest paths
        """
        self.model.removed_nodes[v] = self.model.topology.node[v]
        # First need to remove all links the removed node as endpoint
        neighbors = self.model.topology.adj[v]
        self.model.disconnected_neighbors[v] = set(neighbors.keys())
        for u in self.model.disconnected_neighbors[v]:
            self.remove_link(v, u, recompute_paths=False)
        self.model.topology.remove_node(v)
        if v in self.model.cache:
            self.model.removed_caches[v] = self.model.cache.pop(v)
        if v in self.model.local_cache:
            self.model.removed_local_caches[v] = self.model.local_cache.pop(v)
        if v in self.model.source_node:
            self.model.removed_sources[v] = self.model.source_node.pop(v)
            for content in self.model.removed_sources[v]:
                self.model.countent_source.pop(content)
        if recompute_paths:
            shortest_path = dict(nx.all_pairs_dijkstra_path(self.model.topology))
            self.model.shortest_path = symmetrify_paths(shortest_path)

    def restore_node(self, v, recompute_paths=True):
        """Restore a previously-removed node and update the network model.

        Parameters
        ----------
        v : any hashable type
            Node to restore
        recompute_paths: bool, optional
            If True, recompute all shortest paths
        """
        self.model.topology.add_node(v, **self.model.removed_nodes.pop(v))
        for u in self.model.disconnected_neighbors[v]:
            if (v, u) in self.model.removed_links:
                self.restore_link(v, u, recompute_paths=False)
        self.model.disconnected_neighbors.pop(v)
        if v in self.model.removed_caches:
            self.model.cache[v] = self.model.removed_caches.pop(v)
        if v in self.model.removed_local_caches:
            self.model.local_cache[v] = self.model.removed_local_caches.pop(v)
        if v in self.model.removed_sources:
            self.model.source_node[v] = self.model.removed_sources.pop(v)
            for content in self.model.source_node[v]:
                self.model.countent_source[content] = v
        if recompute_paths:
            shortest_path = dict(nx.all_pairs_dijkstra_path(self.model.topology))
            self.model.shortest_path = symmetrify_paths(shortest_path)

    def reserve_local_cache(self, ratio=0.1):
        """Reserve a fraction of cache as local.

        This method reserves a fixed fraction of the cache of each caching node
        to act as local uncoodinated cache. Methods `get_content` and
        `put_content` will only operated to the coordinated cache. The reserved
        local cache can be accessed with methods `get_content_local_cache` and
        `put_content_local_cache`.

        This function is currently used only by hybrid hash-routing strategies.

        Parameters
        ----------
        ratio : float
            The ratio of cache space to be reserved as local cache.
        """
        if ratio < 0 or ratio > 1:
            raise ValueError("ratio must be between 0 and 1")
        for v, c in list(self.model.cache.items()):
            maxlen = iround(c.maxlen * (1 - ratio))
            if maxlen > 0:
                self.model.cache[v] = type(c)(maxlen)
            else:
                # If the coordinated cache size is zero, then remove cache
                # from that location
                if v in self.model.cache:
                    self.model.cache.pop(v)
            local_maxlen = iround(c.maxlen * (ratio))
            if local_maxlen > 0:
                self.model.local_cache[v] = type(c)(local_maxlen)

    def get_content_local_cache(self, node):
        """Get content from local cache of node (if any)

        Get content from a local cache of a node. Local cache must be
        initialized with the `reserve_local_cache` method.

        Parameters
        ----------
        node : any hashable type
            The node to query
        """
        if node not in self.model.local_cache:
            return False
        cache_hit = self.model.local_cache[node].get(self.session['content'])
        if cache_hit:
            if self.session['log']:
                self.collector.cache_hit(node)
        else:
            if self.session['log']:
                self.collector.cache_miss(node)
        return cache_hit

    def put_content_local_cache(self, node):
        """Put content into local cache of node (if any)

        Put content into a local cache of a node. Local cache must be
        initialized with the `reserve_local_cache` method.

        Parameters
        ----------
        node : any hashable type
            The node to query
        """
        if node in self.model.local_cache:
            return self.model.local_cache[node].put(self.session['content'])


    # LCD operations

    def set_lcd_flow_copied_flag(self, flow, flag):
        """Set the flag indicating copied or not in LCD

        Parameters
        ----------
        flow: Indicating the flow number

        flag : True for already copied
               False for not copied yet
        """
        self.model.lcd_pkt_level_copied_flag[flow] = flag
        # print('model, set flag', self.model.lcd_pkt_level_copied_flag)


    # ProbCache operations

    def start_probcache_c(self, flow):
        """Set the flag indicating copied or not in LCD

        Parameters
        ----------
        flow: Indicating the flow number

        flag : True for already copied
               False for not copied yet
        """
        self.model.ProbCache_c[flow] = 0
        # print('ProbCache start count c', self.model.ProbCache_c[flow])

    def add_probcache_c(self, flow):
        """Set the flag indicating copied or not in LCD

        Parameters
        ----------
        flow: Indicating the flow number

        flag : True for already copied
               False for not copied yet
        """
        self.model.ProbCache_c[flow] += 1
        # print('ProbCache start count c', self.model.ProbCache_c[flow])

    def clear_probcache_c(self, flow):
        """Set the flag indicating copied or not in LCD

        Parameters
        ----------
        flow: Indicating the flow number

        flag : True for already copied
               False for not copied yet
        """
        self.model.ProbCache_c[flow] = 0
        # print('ProbCache start count c', self.model.ProbCache_c[flow])

    def start_probcache_N(self, flow):
        """Set the flag indicating copied or not in LCD

        Parameters
        ----------
        flow: Indicating the flow number

        flag : True for already copied
               False for not copied yet
        """
        self.model.ProbCache_N[flow] = 0
        # print('ProbCache start count c', self.model.ProbCache_c[flow])

    def add_probcache_N(self, flow, n):
        """Set the flag indicating copied or not in LCD

        Parameters
        ----------
        flow: Indicating the flow number

        flag : True for already copied
               False for not copied yet
        """
        self.model.ProbCache_N[flow] += n
        # print('ProbCache start count c', self.model.ProbCache_c[flow])

    def subtract_probcache_N(self, flow, n):
        """Set the flag indicating copied or not in LCD

        Parameters
        ----------
        flow: Indicating the flow number

        flag : True for already copied
               False for not copied yet
        """
        self.model.ProbCache_N[flow] += n
        # print('ProbCache start count c', self.model.ProbCache_c[flow])

    def clear_probcache_N(self, flow):
        """Set the flag indicating copied or not in LCD

        Parameters
        ----------
        flow: Indicating the flow number

        flag : True for already copied
               False for not copied yet
        """
        self.model.ProbCache_N[flow] = 0
        # print('ProbCache start count c', self.model.ProbCache_c[flow])

    def start_probcache_x(self, flow):
        """Set the flag indicating copied or not in LCD

        Parameters
        ----------
        flow: Indicating the flow number

        flag : True for already copied
               False for not copied yet
        """
        self.model.ProbCache_x[flow] = 0.0
        # print('ProbCache start count c', self.model.ProbCache_c[flow])

    def add_probcache_x(self, flow):
        """Set the flag indicating copied or not in LCD

        Parameters
        ----------
        flow: Indicating the flow number

        flag : True for already copied
               False for not copied yet
        """
        self.model.ProbCache_x[flow] += 1
        # print('ProbCache start count c', self.model.ProbCache_c[flow])

    def clear_probcache_x(self, flow):
        """Set the flag indicating copied or not in LCD

        Parameters
        ----------
        flow: Indicating the flow number

        flag : True for already copied
               False for not copied yet
        """
        self.model.ProbCache_x[flow] = 0
        # print('ProbCache start count c', self.model.ProbCache_c[flow])
