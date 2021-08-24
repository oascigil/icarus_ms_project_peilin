"""Implementations of all on-path strategies"""
from __future__ import division
import random

import networkx as nx

from icarus.registry import register_strategy
from icarus.util import inheritdoc, path_links

from .base import Strategy

__all__ = [
       'Partition',
       'Edge',
       'LeaveCopyEverywhere',
       'LeaveCopyEverywherePacketLevel',
       'LeaveCopyEverywherePacketLevelCacheDelay',
       'LeaveCopyDown',
       'LeaveCopyDownPacketLevel',
       'LeaveCopyDownPacketLevelCacheDelay',
       'ProbCache',
       'ProbCachePacketLevel',
       'ProbCachePacketLevelCacheDelay',
       'ProbCachePacketLevelAvoidBusyNode',
       'CacheLessForMore',
       'RandomBernoulli',
       'RandomChoice',
           ]


@register_strategy('PARTITION')
class Partition(Strategy):
    """Partition caching strategy.

    In this strategy the network is divided into as many partitions as the number
    of caching nodes and each receiver is statically mapped to one and only one
    caching node. When a request is issued it is forwarded to the cache mapped
    to the receiver. In case of a miss the request is routed to the source and
    then returned to cache, which will store it and forward it back to the
    receiver.

    This requires median cache placement, which optimizes the placement of
    caches for this strategy.

    This strategy is normally used with a small number of caching nodes. This
    is the the behaviour normally adopted by Network CDN (NCDN). Google Global
    Cache (GGC) operates this way.
    """

    @inheritdoc(Strategy)
    def __init__(self, view, controller):
        super(Partition, self).__init__(view, controller)
        if 'cache_assignment' not in self.view.topology().graph:
            raise ValueError('The topology does not have cache assignment '
                             'information. Have you used the optimal median '
                             'cache assignment?')
        self.cache_assignment = self.view.topology().graph['cache_assignment']

    @inheritdoc(Strategy)
    def process_event(self, time, receiver, content, log):
        source = self.view.content_source(content)
        self.controller.start_session(time, receiver, content, log)
        cache = self.cache_assignment[receiver]
        self.controller.forward_request_path(receiver, cache)
        if not self.controller.get_content(cache):
            self.controller.forward_request_path(cache, source)
            self.controller.get_content(source)
            self.controller.forward_content_path(source, cache)
            self.controller.put_content(cache)
        self.controller.forward_content_path(cache, receiver)
        self.controller.end_session()


@register_strategy('EDGE')
class Edge(Strategy):
    """Edge caching strategy.

    In this strategy only a cache at the edge is looked up before forwarding
    a content request to the original source.

    In practice, this is like an LCE but it only queries the first cache it
    finds in the path. It is assumed to be used with a topology where each
    PoP has a cache but it simulates a case where the cache is actually further
    down the access network and it is not looked up for transit traffic passing
    through the PoP but only for PoP-originated requests.
    """

    @inheritdoc(Strategy)
    def __init__(self, view, controller):
        super(Edge, self).__init__(view, controller)

    @inheritdoc(Strategy)
    def process_event(self, time, receiver, content, log):
        # get all required data
        source = self.view.content_source(content)
        path = self.view.shortest_path(receiver, source)
        # Route requests to original source and queries caches on the path
        self.controller.start_session(time, receiver, content, log)
        edge_cache = None
        for u, v in path_links(path):
            self.controller.forward_request_hop(u, v)
            if self.view.has_cache(v):
                edge_cache = v
                if self.controller.get_content(v):
                    serving_node = v
                else:
                    # Cache miss, get content from source
                    self.controller.forward_request_path(v, source)
                    self.controller.get_content(source)
                    serving_node = source
                break
        else:
            # No caches on the path at all, get it from source
            self.controller.get_content(v)
            serving_node = v

        # Return content
        path = list(reversed(self.view.shortest_path(receiver, serving_node)))
        self.controller.forward_content_path(serving_node, receiver, path)
        if serving_node == source:
            self.controller.put_content(edge_cache)
        self.controller.end_session()

@register_strategy('LCE_PKT_LEVEL')
class LeaveCopyEverywherePacketLevel(Strategy):
    """Leave Copy Everywhere (LCE) packet-level strategy.

    In this strategy a copy of a content is replicated at any cache on the
    path between serving node and receiver.
    """

    @inheritdoc(Strategy)
    def __init__(self, view, controller, **kwargs):
        super(LeaveCopyEverywherePacketLevel, self).__init__(view, controller)

    @inheritdoc(Strategy)
    def process_event(self, time, receiver, content, node, flow, pkt_type, log):
        # get all required data
        # Route requests to original source and queries caches on the path
        if pkt_type == 'Request':
            if node == receiver:
                self.controller.start_flow_session(time, receiver, content, flow, log)
            source = self.view.content_source(content)
            if self.view.has_cache(node) or node == source:
                if self.controller.get_content_flow(node, content, flow, log):
                    # print('flow:', flow, ', cache hit')
                    path = self.view.shortest_path(node, receiver)
                    delay = self.view.link_delay(node, path[1])
                    t_event = time + delay
                    self.controller.forward_request_hop_flow(node, path[1], flow, log)
                    self.controller.add_event({'t_event': t_event, 'receiver': receiver, 'content': content, 'node': path[1], 'flow': flow, 'pkt_type': 'Data', 'log': log} )
                    return
            path = self.view.shortest_path(node, source)
            delay = self.view.link_delay(node, path[1])
            t_event = time + delay
            self.controller.forward_request_hop_flow(node, path[1], flow, log)
            # print('flow:', flow, ', LCE_PKT_LEVEL request')
            self.controller.add_event({'t_event': t_event, 'receiver': receiver, 'content': content, 'node': path[1], 'flow': flow, 'pkt_type': 'Request', 'log': log} )
        elif pkt_type == 'Data':
            if node == receiver:
                # print('flow:', flow, ', LCE_PKT_LEVEL Received')
                self.controller.end_flow_session(flow, log)
            else:
                if self.view.has_cache(node):
                    # print('flow:', flow, ', LCE_PKT_LEVEL put content')
                    self.controller.put_content_flow(node, content, flow)
                path = self.view.shortest_path(node, receiver)
                self.controller.forward_content_hop_flow(node, path[1], flow, log)
                delay = self.view.link_delay(node, path[1])
                t_event = time + delay
                self.controller.add_event({'t_event': t_event, 'receiver': receiver, 'content': content, 'node': path[1], 'flow': flow, 'pkt_type': 'Data', 'log': log})
        else:
            raise ValueError('Invalid packet type')

@register_strategy('LCE_PL_CD')
class LeaveCopyEverywherePacketLevelCacheDelay(Strategy):
    """Leave Copy Everywhere (LCE) packet-level strategy,
       which implement the cache operation delay penalty.

        In this strategy a copy of a content is replicated at any cache on the
        path between serving node and receiver.
    """

    @inheritdoc(Strategy)
    def __init__(self, view, controller, **kwargs):
        super(LeaveCopyEverywherePacketLevelCacheDelay, self).__init__(view, controller)

    @inheritdoc(Strategy)
    def process_event(self, time, receiver, content, node, flow, pkt_type, log):
        # get all required data
        # Route requests to original source and queries caches on the path
        # print(self.view.get_cache_queue_delay_penalty())
        # print('receiver', receiver)
        # print('content', content)
        source = self.view.content_source(content)
        # print('source', source)
        # print('time', time)
        if pkt_type == 'Request':
            if node == receiver:
                self.controller.start_flow_session(time, receiver, content, flow, log)
            # print('node:', node, ', queue length:', len(self.view.cacheQ_node(node)))
            elif ((self.view.has_cache(node) and len(self.view.cacheQ_node(node)) < self.view.get_cache_queue_size()) or node == source) \
                    and self.controller.get_content_flow(node, content, flow, log):
                # path = self.view.shortest_path(node, receiver)
                if node == source:
                    path = self.view.shortest_path(node, receiver)
                    delay = self.view.link_delay(node, path[1])
                    t_event = time + delay
                    # print(flow, 'source add data', t_event)
                    self.controller.forward_content_hop_flow(node, path[1], flow, log)
                    self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                               'content': content, 'node': path[1], 'flow': flow,
                                               'pkt_type': 'Data', 'log': log})
                else:
                    queue_delay = self.view.get_cache_queue_delay(node, time)
                    t_event = time + queue_delay
                    self.controller.cache_operation_flow(flow, queue_delay, log)
                    # print(flow, 'cache hit, add get content', t_event)
                    self.controller.add_cache_queue_event(node, {'t_event': t_event, 'receiver': receiver,
                                                                 'content': content, 'node': node, 'flow': flow,
                                                                 'pkt_type': 'get_content', 'log': log})
                    self.controller.report_cache_queue_size(node, pkt_type, log)
                    self.controller.record_pkt_admitted(node, pkt_type, log)
                return
            elif self.view.has_cache(node) and len(self.view.cacheQ_node(node)) >= self.view.get_cache_queue_size() \
                    and self.controller.get_content_flow(node, content, flow, log):
                self.controller.record_pkt_rejected(node, pkt_type, log)
            path = self.view.shortest_path(node, source)
            delay = self.view.link_delay(node, path[1])
            t_event = time + delay
            # print(flow, 'request add request', t_event)
            self.controller.forward_request_hop_flow(node, path[1], flow, log)
            # print('flow:', flow, ', in request, add request')
            self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                       'content': content, 'node': path[1], 'flow': flow,
                                       'pkt_type': 'Request', 'log': log} )
        elif pkt_type == 'Data':
            if node == receiver:
                # print(flow, ', end session')
                self.controller.end_flow_session_cache_delay(flow, log)
            else:
                if self.view.has_cache(node) and len(self.view.cacheQ_node(node)) < self.view.get_cache_queue_size():
                    queue_delay = self.view.get_cache_queue_delay(node, time)
                    t_event = time + queue_delay
                    self.controller.cache_operation_flow(flow, queue_delay, log)
                    # print(flow, 'in data, add put content', t_event)
                    self.controller.add_cache_queue_event(node, {'t_event': t_event, 'receiver': receiver,
                                                                 'content': content, 'node': node, 'flow': flow,
                                                                 'pkt_type': 'put_content', 'log': log})
                    self.controller.report_cache_queue_size(node, pkt_type, log)
                    self.controller.record_pkt_admitted(node, pkt_type, log)
                    return
                elif self.view.has_cache(node) and len(self.view.cacheQ_node(node)) >= self.view.get_cache_queue_size():
                        self.controller.record_pkt_rejected(node, pkt_type, log)
                path = self.view.shortest_path(node, receiver)
                delay = self.view.link_delay(node, path[1])
                t_event = time + delay
                # print(flow, 'data add data', t_event)
                self.controller.forward_content_hop_flow(node, path[1], flow, log)
                # print('flow:', flow, ', in data, add data')
                self.controller.add_event( {'t_event': t_event, 'receiver': receiver,
                                            'content': content, 'node': path[1], 'flow': flow,
                                            'pkt_type': 'Data', 'log': log})
        elif pkt_type == 'get_content':
            # add the get operation
            path = self.view.shortest_path(node, receiver)
            delay = self.view.link_delay(node, path[1])
            t_event = time + delay
            # print(flow, ', get content add data', t_event)
            self.controller.forward_content_hop_flow(node, path[1], flow, log)
            self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                       'content': content, 'node': path[1], 'flow': flow,
                                       'pkt_type': 'Data', 'log': log})
        elif pkt_type == 'put_content':
            # put content delay
            self.controller.put_content_flow(node, content, flow)
            path = self.view.shortest_path(node, receiver)
            delay = self.view.link_delay(node, path[1])
            t_event = time + delay
            # print(flow, ', put content add data',t_event)
            self.controller.forward_content_hop_flow(node, path[1], flow, log)
            self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                       'content': content, 'node': path[1], 'flow': flow,
                                       'pkt_type': 'Data', 'log': log})
        else:
            raise ValueError('Invalid packet type')

@register_strategy('LCE_AVOID_BUSY_NODE')
class LeaveCopyEverywherePacketLevelAvoidBusyNode(Strategy):
    """Leave Copy Everywhere (LCE) packet-level strategy,
       which implement the cache operation delay penalty.

        In this strategy a copy of a content is replicated at any cache on the
        path between serving node and receiver.
    """

    @inheritdoc(Strategy)
    def __init__(self, view, controller, **kwargs):
        super(LeaveCopyEverywherePacketLevelAvoidBusyNode, self).__init__(view, controller)

    @inheritdoc(Strategy)
    def process_event(self, time, receiver, content, node, flow, pkt_type, log):
        # get all required data
        # Route requests to original source and queries caches on the path
        # print(self.view.get_cache_queue_delay_penalty())
        # print('receiver', receiver)
        # print('content', content)
        source = self.view.content_source(content)
        # print('source', source)
        # print('time', time)
        if pkt_type == 'Request':
            if node == receiver:
                self.controller.start_flow_session(time, receiver, content, flow, log)
            # print('node:', node, ', queue length:', len(self.view.cacheQ_node(node)))
            elif ((self.view.has_cache(node) and len(self.view.cacheQ_node(node)) < self.view.get_cache_queue_size()) or node == source) \
                    and self.controller.get_content_flow(node, content, flow, log):
                # path = self.view.shortest_path(node, receiver)
                if node == source:
                    path = self.view.shortest_path(node, receiver)
                    delay = self.view.link_delay(node, path[1])
                    t_event = time + delay
                    # print(flow, 'source add data', t_event)
                    self.controller.forward_content_hop_flow(node, path[1], flow, log)
                    self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                               'content': content, 'node': path[1], 'flow': flow,
                                               'pkt_type': 'Data', 'log': log})
                else:
                    queue_delay = self.view.get_cache_queue_delay(node, time)
                    t_event = time + queue_delay
                    self.controller.cache_operation_flow(flow, queue_delay, log)
                    # print(flow, 'cache hit, add get content', t_event)
                    self.controller.add_cache_queue_event(node, {'t_event': t_event, 'receiver': receiver,
                                                                 'content': content, 'node': node, 'flow': flow,
                                                                 'pkt_type': 'get_content', 'log': log})
                    self.controller.report_cache_queue_size(node, pkt_type, log)
                    self.controller.record_pkt_admitted(node, pkt_type, log)
                return
            elif self.view.has_cache(node) and len(self.view.cacheQ_node(node)) >= self.view.get_cache_queue_size() \
                    and self.controller.get_content_flow(node, content, flow, log):
                self.controller.record_pkt_rejected(node, pkt_type, log)
                self.controller.track_busy_node(flow, node, log)
            path = self.view.shortest_path(node, source)
            delay = self.view.link_delay(node, path[1])
            t_event = time + delay
            # print(flow, 'request add request', t_event)
            self.controller.forward_request_hop_flow(node, path[1], flow, log)
            # print('flow:', flow, ', in request, add request')
            self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                       'content': content, 'node': path[1], 'flow': flow,
                                       'pkt_type': 'Request', 'log': log} )
        elif pkt_type == 'Data':
            if node == receiver:
                # print(flow, ', end session')
                self.controller.end_flow_session_cache_delay(flow, log)
            else:
                if self.view.has_cache(node) \
                        and len(self.view.cacheQ_node(node)) < self.view.get_cache_queue_size() \
                        and (node not in self.view.track_busy_node(flow)):
                    queue_delay = self.view.get_cache_queue_delay(node, time)
                    t_event = time + queue_delay
                    self.controller.cache_operation_flow(flow, queue_delay, log)
                    # print(flow, 'in data, add put content', t_event)
                    self.controller.add_cache_queue_event(node, {'t_event': t_event, 'receiver': receiver,
                                                                 'content': content, 'node': node, 'flow': flow,
                                                                 'pkt_type': 'put_content', 'log': log})
                    self.controller.report_cache_queue_size(node, pkt_type, log)
                    self.controller.record_pkt_admitted(node, pkt_type, log)
                    return
                elif self.view.has_cache(node) \
                        and (len(self.view.cacheQ_node(node)) >= self.view.get_cache_queue_size() or node in self.view.track_busy_node(flow)):
                        self.controller.record_pkt_rejected(node, pkt_type, log)
                path = self.view.shortest_path(node, receiver)
                delay = self.view.link_delay(node, path[1])
                t_event = time + delay
                # print(flow, 'data add data', t_event)
                self.controller.forward_content_hop_flow(node, path[1], flow, log)
                # print('flow:', flow, ', in data, add data')
                self.controller.add_event( {'t_event': t_event, 'receiver': receiver,
                                            'content': content, 'node': path[1], 'flow': flow,
                                            'pkt_type': 'Data', 'log': log})
        elif pkt_type == 'get_content':
            # add the get operation
            path = self.view.shortest_path(node, receiver)
            delay = self.view.link_delay(node, path[1])
            t_event = time + delay
            # print(flow, ', get content add data', t_event)
            self.controller.forward_content_hop_flow(node, path[1], flow, log)
            self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                       'content': content, 'node': path[1], 'flow': flow,
                                       'pkt_type': 'Data', 'log': log})
        elif pkt_type == 'put_content':
            # put content delay
            self.controller.put_content_flow(node, content, flow)
            path = self.view.shortest_path(node, receiver)
            delay = self.view.link_delay(node, path[1])
            t_event = time + delay
            # print(flow, ', put content add data',t_event)
            self.controller.forward_content_hop_flow(node, path[1], flow, log)
            self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                       'content': content, 'node': path[1], 'flow': flow,
                                       'pkt_type': 'Data', 'log': log})
        else:
            raise ValueError('Invalid packet type')


@register_strategy('LCE')
class LeaveCopyEverywhere(Strategy):
    """Leave Copy Everywhere (LCE) strategy.

    In this strategy a copy of a content is replicated at any cache on the
    path between serving node and receiver.
    """

    @inheritdoc(Strategy)
    def __init__(self, view, controller, **kwargs):
        super(LeaveCopyEverywhere, self).__init__(view, controller)

    @inheritdoc(Strategy)
    def process_event(self, time, receiver, content, log):
        # print('LCE process event')
        # get all required data
        source = self.view.content_source(content)
        path = self.view.shortest_path(receiver, source)
        # Route requests to original source and queries caches on the path
        self.controller.start_session(time, receiver, content, log)
        for u, v in path_links(path):
            self.controller.forward_request_hop(u, v)
            if self.view.has_cache(v):
                if self.controller.get_content(v):
                    # print('LCE cache hit')
                    serving_node = v
                    break
        else:
            # No cache hits, get content from source
            self.controller.get_content(v)
            # print('LCE find source')
            serving_node = v
        # Return content
        path = list(reversed(self.view.shortest_path(receiver, serving_node)))
        for u, v in path_links(path):
            self.controller.forward_content_hop(u, v)
            if self.view.has_cache(v):
                # insert content
                # print('LCE copy content')
                self.controller.put_content(v)
        # print('LCE Received')
        self.controller.end_session()


@register_strategy('LCD')
class LeaveCopyDown(Strategy):
    """Leave Copy Down (LCD) strategy.

    According to this strategy, one copy of a content is replicated only in
    the caching node you hop away from the serving node in the direction of
    the receiver. This strategy is described in [2]_.

    Rereferences
    ------------
    ..[1] N. Laoutaris, H. Che, i. Stavrakakis, The LCD interconnection of LRU
          caches and its analysis.
          Available: http://cs-people.bu.edu/nlaout/analysis_PEVA.pdf
    """

    @inheritdoc(Strategy)
    def __init__(self, view, controller, **kwargs):
        super(LeaveCopyDown, self).__init__(view, controller)

    @inheritdoc(Strategy)
    def process_event(self, time, receiver, content, log):
        # print('LCD process_event')
        # get all required data
        source = self.view.content_source(content)
        path = self.view.shortest_path(receiver, source)
        # Route requests to original source and queries caches on the path
        self.controller.start_session(time, receiver, content, log)
        for u, v in path_links(path):
            self.controller.forward_request_hop(u, v)
            if self.view.has_cache(v):
                if self.controller.get_content(v):
                    # print('LCD cache hit')
                    serving_node = v
                    break
        else:
            # No cache hits, get content from source
            self.controller.get_content(v)
            # print('LCD find source')
            serving_node = v
        # Return content
        path = list(reversed(self.view.shortest_path(receiver, serving_node)))
        # Leave a copy of the content only in the cache one level down the hit
        # caching node
        copied = False
        for u, v in path_links(path):
            self.controller.forward_content_hop(u, v)
            if not copied and v != receiver and self.view.has_cache(v):
                self.controller.put_content(v)
                # print('LCD copy content')
                copied = True
        # print('LCD Received')
        self.controller.end_session()


@register_strategy('LCD_PKT_LEVEL')
class LeaveCopyDownPacketLevel (Strategy):
    """Leave Copy Down (LCD) strategy.

        According to this strategy, one copy of a content is replicated only in
        the caching node you hop away from the serving node in the direction of
        the receiver. This strategy is described in [2]_.

        Rereferences
        ------------
        ..[1] N. Laoutaris, H. Che, i. Stavrakakis, The LCD interconnection of LRU
              caches and its analysis.
              Available: http://cs-people.bu.edu/nlaout/analysis_PEVA.pdf
        """

    @inheritdoc(Strategy)
    def __init__(self, view, controller, **kwargs):
        super(LeaveCopyDownPacketLevel, self).__init__(view, controller)

    @inheritdoc(Strategy)
    def process_event(self, time, receiver, content, node, flow, pkt_type, log):
        # get all required data
        # Route requests to original source and queries cache on the path
        if pkt_type == 'Request':
            if node == receiver:
                self.controller.set_lcd_flow_copied_flag(flow, False)
                # print('flow:', flow, ', start session flag', self.view.get_lcd_flow_copied_flag(flow))
                self.controller.start_flow_session(time, receiver, content, flow, log)
            source = self.view.content_source(content)
            if self.view.has_cache(node) or node == source:
                if self.controller.get_content_flow(node, content, flow, log):
                    path = self.view.shortest_path(node, receiver)
                    delay = self.view.link_delay(node, path[1])
                    t_event = time + delay
                    self.controller.forward_request_hop_flow(node, path[1], flow, log)
                    # self.controller.set_lcd_flow_copied_flag(flow, False)
                    # print('flow:', flow, ', cache hit, flag', self.view.get_lcd_flow_copied_flag(flow))
                    self.controller.add_event({'t_event': t_event, 'receiver': receiver, 'content': content, 'node': path[1], 'flow': flow, 'pkt_type': 'Data', 'log': log})
                    return
            path = self.view.shortest_path(node, source)
            delay = self.view.link_delay(node, path[1])
            t_event = time + delay
            self.controller.forward_request_hop_flow(node, path[1], flow ,log)
            # print('flow:', flow, ', Request, flag', self.view.get_lcd_flow_copied_flag(flow))
            self.controller.add_event({'t_event': t_event, 'receiver': receiver, 'content': content, 'node': path[1], 'flow': flow, 'pkt_type': 'Request', 'log': log})

        # Leave a copy of the content only in the cache one level down the hit
        # caching node
        elif pkt_type == 'Data':
            if node == receiver:
                # print('flow:', flow, ', LCD_PKT_LEVEL Received')
                self.controller.set_lcd_flow_copied_flag(flow, False)
                self.controller.end_flow_session(flow, log)
            else:
                if self.view.has_cache(node) and self.view.get_lcd_flow_copied_flag(flow) == False:
                    self.controller.put_content_flow(node, content, flow)
                    self.controller.set_lcd_flow_copied_flag(flow, True)
                    # print('flow:', flow, ', set to true !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                path = self.view.shortest_path(node, receiver)
                self.controller.forward_content_hop_flow(node, path[1], flow, log)
                delay = self.view.link_delay(node, path[1])
                t_event = time + delay
                # print('flow:', flow, ', Data, flag', self.view.get_lcd_flow_copied_flag(flow))
                self.controller.add_event({'t_event': t_event, 'receiver': receiver, 'content': content, 'node': path[1], 'flow': flow, 'pkt_type': 'Data', 'log': log})
        else:
            raise ValueError('Invalid packet type')


@register_strategy('LCD_PL_CD')
class LeaveCopyDownPacketLevelCacheDelay(Strategy):
    """Leave Copy Down (LCD) packet-level strategy,
       which implement the cache operation delay penalty.

        According to this strategy, one copy of a content is replicated only in
        the caching node you hop away from the serving node in the direction of
        the receiver. This strategy is described in [2]_.

        Rereferences
        ------------
        ..[1] N. Laoutaris, H. Che, i. Stavrakakis, The LCD interconnection of LRU
              caches and its analysis.
              Available: http://cs-people.bu.edu/nlaout/analysis_PEVA.pdf
    """

    @inheritdoc(Strategy)
    def __init__(self, view, controller, **kwargs):
        super(LeaveCopyDownPacketLevelCacheDelay, self).__init__(view, controller)

    @inheritdoc(Strategy)
    def process_event(self, time, receiver, content, node, flow, pkt_type, log):
        # get all required data
        # Route requests to original source and queries caches on the path
        source = self.view.content_source(content)
        if pkt_type == 'Request':
            if node == receiver:
                self.controller.set_lcd_flow_copied_flag(flow, False)
                self.controller.start_flow_session(time, receiver, content, flow, log)
                # print('node:', node, ', queue length:', len(self.view.cacheQ_node(node)))
            elif ((self.view.has_cache(node) and len(self.view.cacheQ_node(node)) < self.view.get_cache_queue_size()) or node == source) \
                    and self.controller.get_content_flow(node, content, flow, log):
                if node == source:
                    path = self.view.shortest_path(node, receiver)
                    delay = self.view.link_delay(node, path[1])
                    t_event = time + delay
                    # print(flow, 'source add data', t_event)
                    # print('flow:', flow, ', in get_content, add data')
                    self.controller.forward_content_hop_flow(node, path[1], flow, log)
                    self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                               'content': content, 'node': path[1], 'flow': flow,
                                               'pkt_type': 'Data', 'log': log})
                else:
                    queue_delay = self.view.get_cache_queue_delay(node, time)
                    t_event = time + queue_delay
                    self.controller.cache_operation_flow(flow, queue_delay, log)
                    # print('in request, add get content', t_event)
                    self.controller.add_cache_queue_event(node, {'t_event': t_event, 'receiver': receiver,
                                                                 'content': content, 'node': node, 'flow': flow,
                                                                 'pkt_type': 'get_content', 'log': log})
                    self.controller.report_cache_queue_size(node, pkt_type, log)
                    self.controller.record_pkt_admitted(node, pkt_type, log)
                return
            elif self.view.has_cache(node) and len(self.view.cacheQ_node(node)) >= self.view.get_cache_queue_size() \
                    and self.controller.get_content_flow(node, content, flow, log):
                self.controller.record_pkt_rejected(node, pkt_type, log)
            path = self.view.shortest_path(node, source)
            delay = self.view.link_delay(node, path[1])
            t_event = time + delay
            self.controller.forward_request_hop_flow(node, path[1], flow, log)
            # print('flow:', flow, ', in request, add request')
            self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                       'content': content, 'node': path[1], 'flow': flow,
                                       'pkt_type': 'Request', 'log': log} )
        elif pkt_type == 'Data':
            if node == receiver:
                # print('flow:', flow, ', end session')
                self.controller.set_lcd_flow_copied_flag(flow, False)
                self.controller.end_flow_session_cache_delay(flow, log)
            else:
                if self.view.has_cache(node) and len(self.view.cacheQ_node(node)) < self.view.get_cache_queue_size() \
                        and self.view.get_lcd_flow_copied_flag(flow) == False:
                    self.controller.set_lcd_flow_copied_flag(flow, True)
                    queue_delay = self.view.get_cache_queue_delay(node, time)
                    t_event = time + queue_delay
                    self.controller.cache_operation_flow(flow, queue_delay, log)
                    # print(flow, 'in data, add put content', t_event)
                    self.controller.add_cache_queue_event(node, {'t_event': t_event, 'receiver': receiver,
                                                                 'content': content, 'node': node, 'flow': flow,
                                                                 'pkt_type': 'put_content', 'log': log})
                    self.controller.report_cache_queue_size(node, pkt_type, log)
                    self.controller.record_pkt_admitted(node, pkt_type, log)
                    return
                elif self.view.has_cache(node) and len(self.view.cacheQ_node(node)) >= self.view.get_cache_queue_size() \
                        and self.view.get_lcd_flow_copied_flag(flow) == False:
                        self.controller.record_pkt_rejected(node, pkt_type, log)
                path = self.view.shortest_path(node, receiver)
                delay = self.view.link_delay(node, path[1])
                t_event = time + delay
                self.controller.forward_content_hop_flow(node, path[1], flow, log)
                # print('flow:', flow, ', in data, add data')
                self.controller.add_event( {'t_event': t_event, 'receiver': receiver,
                                            'content': content, 'node': path[1], 'flow': flow,
                                            'pkt_type': 'Data', 'log': log})
        elif pkt_type == 'get_content':
            # add the get operation
            path = self.view.shortest_path(node, receiver)
            delay = self.view.link_delay(node, path[1])
            t_event = time + delay
            # print('flow:', flow, ', get content add data', t_event)
            self.controller.forward_content_hop_flow(node, path[1], flow, log)
            self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                        'content': content, 'node': path[1], 'flow': flow,
                                        'pkt_type': 'Data', 'log': log})
        elif pkt_type == 'put_content':
            # put content delay
            self.controller.put_content_flow(node, content, flow)
            path = self.view.shortest_path(node, receiver)
            delay = self.view.link_delay(node, path[1])
            t_event = time + delay
            # print('flow:', flow, ', put content add data',t_event)
            self.controller.forward_content_hop_flow(node, path[1], flow, log)
            self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                       'content': content, 'node': path[1], 'flow': flow,
                                       'pkt_type': 'Data', 'log': log})
        else:
            raise ValueError('Invalid packet type')


@register_strategy('LCD_AVOID_BUSY_NODE')
class LeaveCopyDownPacketLevelAvoidBusyNode(Strategy):
    """Leave Copy Down (LCD) packet-level strategy,
       which implement the cache operation delay penalty.

        According to this strategy, one copy of a content is replicated only in
        the caching node you hop away from the serving node in the direction of
        the receiver. This strategy is described in [2]_.

        Rereferences
        ------------
        ..[1] N. Laoutaris, H. Che, i. Stavrakakis, The LCD interconnection of LRU
              caches and its analysis.
              Available: http://cs-people.bu.edu/nlaout/analysis_PEVA.pdf
    """

    @inheritdoc(Strategy)
    def __init__(self, view, controller, **kwargs):
        super(LeaveCopyDownPacketLevelAvoidBusyNode, self).__init__(view, controller)

    @inheritdoc(Strategy)
    def process_event(self, time, receiver, content, node, flow, pkt_type, log):
        # get all required data
        # Route requests to original source and queries caches on the path
        source = self.view.content_source(content)
        if pkt_type == 'Request':
            if node == receiver:
                self.controller.set_lcd_flow_copied_flag(flow, False)
                self.controller.start_flow_session(time, receiver, content, flow, log)
                # print('node:', node, ', queue length:', len(self.view.cacheQ_node(node)))
            elif ((self.view.has_cache(node) and len(self.view.cacheQ_node(node)) < self.view.get_cache_queue_size()) or node == source) \
                    and self.controller.get_content_flow(node, content, flow, log):
                if node == source:
                    path = self.view.shortest_path(node, receiver)
                    delay = self.view.link_delay(node, path[1])
                    t_event = time + delay
                    # print(flow, 'source add data', t_event)
                    # print('flow:', flow, ', in get_content, add data')
                    self.controller.forward_content_hop_flow(node, path[1], flow, log)
                    self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                               'content': content, 'node': path[1], 'flow': flow,
                                               'pkt_type': 'Data', 'log': log})
                else:
                    queue_delay = self.view.get_cache_queue_delay(node, time)
                    t_event = time + queue_delay
                    self.controller.cache_operation_flow(flow, queue_delay, log)
                    # print('in request, add get content', t_event)
                    self.controller.add_cache_queue_event(node, {'t_event': t_event, 'receiver': receiver,
                                                                 'content': content, 'node': node, 'flow': flow,
                                                                 'pkt_type': 'get_content', 'log': log})
                    self.controller.report_cache_queue_size(node, pkt_type, log)
                    self.controller.record_pkt_admitted(node, pkt_type, log)
                return
            elif self.view.has_cache(node) and len(self.view.cacheQ_node(node)) >= self.view.get_cache_queue_size() \
                    and self.controller.get_content_flow(node, content, flow, log):
                self.controller.record_pkt_rejected(node, pkt_type, log)
                self.controller.track_busy_node(flow, node, log)
            path = self.view.shortest_path(node, source)
            delay = self.view.link_delay(node, path[1])
            t_event = time + delay
            self.controller.forward_request_hop_flow(node, path[1], flow, log)
            # print('flow:', flow, ', in request, add request')
            self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                       'content': content, 'node': path[1], 'flow': flow,
                                       'pkt_type': 'Request', 'log': log} )
        elif pkt_type == 'Data':
            if node == receiver:
                # print('flow:', flow, ', end session')
                self.controller.set_lcd_flow_copied_flag(flow, False)
                self.controller.end_flow_session_cache_delay(flow, log)
            else:
                if self.view.has_cache(node) and len(self.view.cacheQ_node(node)) < self.view.get_cache_queue_size() \
                        and self.view.get_lcd_flow_copied_flag(flow) == False \
                        and (node not in self.view.track_busy_node(flow)):
                    self.controller.set_lcd_flow_copied_flag(flow, True)
                    queue_delay = self.view.get_cache_queue_delay(node, time)
                    t_event = time + queue_delay
                    self.controller.cache_operation_flow(flow, queue_delay, log)
                    # print(flow, 'in data, add put content', t_event)
                    self.controller.add_cache_queue_event(node, {'t_event': t_event, 'receiver': receiver,
                                                                 'content': content, 'node': node, 'flow': flow,
                                                                 'pkt_type': 'put_content', 'log': log})
                    self.controller.report_cache_queue_size(node, pkt_type, log)
                    self.controller.record_pkt_admitted(node, pkt_type, log)
                    return
                elif self.view.has_cache(node) and self.view.get_lcd_flow_copied_flag(flow) == False \
                        and (len(self.view.cacheQ_node(node)) >= self.view.get_cache_queue_size() or node in self.view.track_busy_node(flow)):
                        self.controller.record_pkt_rejected(node, pkt_type, log)
                path = self.view.shortest_path(node, receiver)
                delay = self.view.link_delay(node, path[1])
                t_event = time + delay
                self.controller.forward_content_hop_flow(node, path[1], flow, log)
                # print('flow:', flow, ', in data, add data')
                self.controller.add_event( {'t_event': t_event, 'receiver': receiver,
                                            'content': content, 'node': path[1], 'flow': flow,
                                            'pkt_type': 'Data', 'log': log})
        elif pkt_type == 'get_content':
            # add the get operation
            path = self.view.shortest_path(node, receiver)
            delay = self.view.link_delay(node, path[1])
            t_event = time + delay
            # print('flow:', flow, ', get content add data', t_event)
            self.controller.forward_content_hop_flow(node, path[1], flow, log)
            self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                        'content': content, 'node': path[1], 'flow': flow,
                                        'pkt_type': 'Data', 'log': log})
        elif pkt_type == 'put_content':
            # put content delay
            self.controller.put_content_flow(node, content, flow)
            path = self.view.shortest_path(node, receiver)
            delay = self.view.link_delay(node, path[1])
            t_event = time + delay
            # print('flow:', flow, ', put content add data',t_event)
            self.controller.forward_content_hop_flow(node, path[1], flow, log)
            self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                       'content': content, 'node': path[1], 'flow': flow,
                                       'pkt_type': 'Data', 'log': log})
        else:
            raise ValueError('Invalid packet type')


@register_strategy('PROB_CACHE')
class ProbCache(Strategy):
    """ProbCache strategy [3]_

    This strategy caches content objects probabilistically on a path with a
    probability depending on various factors, including distance from source
    and destination and caching space available on the path.

    This strategy was originally proposed in [2]_ and extended in [3]_. This
    class implements the extended version described in [3]_. In the extended
    version of ProbCache the :math`x/c` factor of the ProbCache equation is
    raised to the power of :math`c`.

    References
    ----------
    ..[2] I. Psaras, W. Chai, G. Pavlou, Probabilistic In-Network Caching for
          Information-Centric Networks, in Proc. of ACM SIGCOMM ICN '12
          Available: http://www.ee.ucl.ac.uk/~uceeips/prob-cache-icn-sigcomm12.pdf
    ..[3] I. Psaras, W. Chai, G. Pavlou, In-Network Cache Management and
          Resource Allocation for Information-Centric Networks, IEEE
          Transactions on Parallel and Distributed Systems, 22 May 2014
          Available: http://doi.ieeecomputersociety.org/10.1109/TPDS.2013.304
    """

    @inheritdoc(Strategy)
    def __init__(self, view, controller, t_tw=10):
        super(ProbCache, self).__init__(view, controller)
        self.t_tw = t_tw
        self.cache_size = view.cache_nodes(size=True)

    @inheritdoc(Strategy)
    def process_event(self, time, receiver, content, log):
        # get all required data
        source = self.view.content_source(content)
        path = self.view.shortest_path(receiver, source)
        # Route requests to original source and queries caches on the path
        self.controller.start_session(time, receiver, content, log)
        for hop in range(1, len(path)):
            u = path[hop - 1]
            v = path[hop]
            self.controller.forward_request_hop(u, v)
            if self.view.has_cache(v):
                if self.controller.get_content(v):
                    serving_node = v
                    break
        else:
            # No cache hits, get content from source
            self.controller.get_content(v)
            serving_node = v
        # Return content
        path = list(reversed(self.view.shortest_path(receiver, serving_node)))
        c = len([node for node in path if self.view.has_cache(node)])
        x = 0.0
        for hop in range(1, len(path)):
            u = path[hop - 1]
            v = path[hop]
            N = sum([self.cache_size[n] for n in path[hop - 1:]
                     if n in self.cache_size])
            if v in self.cache_size:
                x += 1
            self.controller.forward_content_hop(u, v)
            if v != receiver and v in self.cache_size:
                # The (x/c) factor raised to the power of "c" according to the
                # extended version of ProbCache published in IEEE TPDS
                prob_cache = float(N) / (self.t_tw * self.cache_size[v]) * (x / c) ** c
                if random.random() < prob_cache:
                    self.controller.put_content(v)
        self.controller.end_session()


@register_strategy('PROB_CACHE_PKT_LEVEL')
class ProbCachePacketLevel(Strategy):
    """ProbCache strategy [3]_

    This strategy caches content objects probabilistically on a path with a
    probability depending on various factors, including distance from source
    and destination and caching space available on the path.

    This strategy was originally proposed in [2]_ and extended in [3]_. This
    class implements the extended version described in [3]_. In the extended
    version of ProbCache the :math`x/c` factor of the ProbCache equation is
    raised to the power of :math`c`.

    References
    ----------
    ..[2] I. Psaras, W. Chai, G. Pavlou, Probabilistic In-Network Caching for
          Information-Centric Networks, in Proc. of ACM SIGCOMM ICN '12
          Available: http://www.ee.ucl.ac.uk/~uceeips/prob-cache-icn-sigcomm12.pdf
    ..[3] I. Psaras, W. Chai, G. Pavlou, In-Network Cache Management and
          Resource Allocation for Information-Centric Networks, IEEE
          Transactions on Parallel and Distributed Systems, 22 May 2014
          Available: http://doi.ieeecomputersociety.org/10.1109/TPDS.2013.304
    """

    @inheritdoc(Strategy)
    def __init__(self, view, controller, t_tw=10):
        super(ProbCachePacketLevel, self).__init__(view, controller)
        self.t_tw = t_tw
        self.cache_size = view.cache_nodes(size=True)

    @inheritdoc(Strategy)
    def process_event(self, time, receiver, content, node, flow, pkt_type, log):
        # print('ProbCache_PKT_LEVEL process_event')
        # get all required data
        # Route requests to original source and queries cache on the path
        if pkt_type == 'Request':
            if node == receiver:
                # print('flow:', flow, ', ProbCache_PKT_LEVEL start session')
                self.controller.start_flow_session(time, receiver, content, flow, log)
                self.controller.start_probcache_c(flow)
                # print('flow:', flow, 'c:', self.view.get_probcache_c(flow))
                self.controller.start_probcache_N(flow)
                # print('flow:', flow, 'N:', self.view.get_probcache_N(flow))
            source = self.view.content_source(content)
            if (node in self.cache_size) or node == source:
                if self.controller.get_content_flow(node, content, flow, log):
                    if node in self.cache_size:
                        self.controller.add_probcache_c(flow)
                        self.controller.add_probcache_N(flow, self.cache_size[node])
                    path = self.view.shortest_path(node, receiver)
                    delay = self.view.link_delay(node, path[1])
                    t_event = time + delay
                    self.controller.forward_content_hop_flow(node, path[1], flow, log)
                    self.controller.start_probcache_x(flow)
                    # print('flow:', flow, ', cache hit')
                    self.controller.add_event( {'t_event': t_event, 'receiver': receiver, 'content': content, 'node': path[1], 'flow': flow,
                         'pkt_type': 'Data', 'log': log})
                    # print('flow:', flow, ', node', node)
                    return
            path = self.view.shortest_path(node, source)
            delay = self.view.link_delay(node, path[1])
            t_event = time + delay
            self.controller.forward_request_hop_flow(node, path[1], flow, log)
            if node in self.cache_size:
                self.controller.add_probcache_c(flow)
                self.controller.add_probcache_N(flow, self.cache_size[node])
                # print('flow:', flow, 'c', self.view.get_probcache_c(flow))
                # print('flow:', flow, 'path[1]:', path[1], 'add N', self.cache_size[path[1]])
                # print('flow:', flow, 'N', self.view.get_probcache_N(flow))
            # print('flow:', flow, ', Request')
            self.controller.add_event({'t_event': t_event, 'receiver': receiver, 'content': content, 'node': path[1], 'flow': flow,
                 'pkt_type': 'Request', 'log': log})
            # print('flow:', flow, ', node,', node)
        # Return content
        elif pkt_type == 'Data':
            if node == receiver:
                # self.controller.clear_probcahce_c
                # self.controller.clear_probcahce_N
                # self.controller.clear_probcahce_x
                # print('flow:', flow, ', ProbCache_PKT_LEVEL Received')
                self.controller.end_flow_session(flow, log)
            else:
                path = self.view.shortest_path(node, receiver)
                source = self.view.content_source(content)
                path_to_source = self.view.shortest_path(node, source)
                if node in self.cache_size:
                    self.controller.add_probcache_x(flow)
                    # print('flow:', flow, 'x', self.view.get_probcache_x(flow))
                    # The (x/c) factor raised to the power of "c" according to the
                    # extended version of ProbCache published in IEEE TPDS
                    N = self.view.get_probcache_N(flow)
                    x = self.view.get_probcache_x(flow)
                    c = self.view.get_probcache_c(flow)
                    prob_cache = float(N) / (self.t_tw * self.cache_size[node]) * (x / c) ** c
                    if random.random() < prob_cache:
                        # print('flow:', flow, 'ProbCache_PKT_LEVEL make a copy')
                        self.controller.put_content_flow(node, content, flow)
                if path_to_source[1] in self.cache_size:
                    self.controller.subtract_probcache_N(flow, self.cache_size[path_to_source[1]])
                    # print('flow,', flow, 'N:', self.view.get_probcache_N(flow))
                self.controller.forward_content_hop_flow(node, path[1], flow, log)
                delay = self.view.link_delay(node, path[1])
                t_event = time + delay
                self.controller.add_event({'t_event': t_event, 'receiver': receiver, 'content': content, 'node': path[1], 'flow': flow, 'pkt_type': 'Data', 'log': log})
                # print('flow:', flow, ', node', node)
        else:
            raise ValueError('Invalid packet type')


@register_strategy('PROB_CACHE_PL_CD')
class ProbCachePacketLevelCacheDelay(Strategy):
    """ProbCache strategy [3]_

    This strategy caches content objects probabilistically on a path with a
    probability depending on various factors, including distance from source
    and destination and caching space available on the path.

    This strategy was originally proposed in [2]_ and extended in [3]_. This
    class implements the extended version described in [3]_. In the extended
    version of ProbCache the :math`x/c` factor of the ProbCache equation is
    raised to the power of :math`c`.

    References
    ----------
    ..[2] I. Psaras, W. Chai, G. Pavlou, Probabilistic In-Network Caching for
          Information-Centric Networks, in Proc. of ACM SIGCOMM ICN '12
          Available: http://www.ee.ucl.ac.uk/~uceeips/prob-cache-icn-sigcomm12.pdf
    ..[3] I. Psaras, W. Chai, G. Pavlou, In-Network Cache Management and
          Resource Allocation for Information-Centric Networks, IEEE
          Transactions on Parallel and Distributerd Systems, 22 May 2014
          Available: http://doi.ieeecomputersociety.org/10.1109/TPDS.2013.304
    """

    @inheritdoc(Strategy)
    def __init__(self, view, controller, t_tw=10):
        super(ProbCachePacketLevelCacheDelay, self).__init__(view, controller)
        self.t_tw = t_tw
        self.cache_size = view.cache_nodes(size=True)

    @inheritdoc(Strategy)
    def process_event(self, time, receiver, content, node, flow, pkt_type, log):
        # get all required data
        # Route requests to original source and queries caches on the path
        source = self.view.content_source(content)
        if pkt_type == 'Request':
            if node == receiver:
                self.controller.start_flow_session(time, receiver, content, flow, log)
                self.controller.start_probcache_c(flow)
                self.controller.start_probcache_N(flow)
            elif (((node in self.cache_size) and len(self.view.cacheQ_node(node)) < self.view.get_cache_queue_size()) or node == source) \
                    and self.controller.get_content_flow(node, content, flow, log):
                if node in self.cache_size:
                    self.controller.add_probcache_c(flow)
                    self.controller.add_probcache_N(flow, self.cache_size[node])
                    # path = self.view.shortest_path(node, receiver)
                if node == source:
                    path = self.view.shortest_path(node, receiver)
                    delay = self.view.link_delay(node, path[1])
                    t_event = time + delay
                    self.controller.forward_content_hop_flow(node, path[1], flow, log)
                    self.controller.start_probcache_x(flow)
                    self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                               'content': content, 'node': path[1], 'flow': flow,
                                               'pkt_type': 'Data', 'log': log})
                else:
                    queue_delay = self.view.get_cache_queue_delay(node, time)
                    t_event = time + queue_delay
                    self.controller.cache_operation_flow(flow, queue_delay, log)
                    self.controller.start_probcache_x(flow)
                    self.controller.add_cache_queue_event(node, {'t_event': t_event, 'receiver': receiver,
                                                                 'content': content, 'node': node, 'flow': flow,
                                                                 'pkt_type': 'get_content', 'log': log})
                    self.controller.report_cache_queue_size(node, pkt_type, log)
                    self.controller.record_pkt_admitted(node, pkt_type, log)
                return
            elif (node in self.cache_size) and len(self.view.cacheQ_node(node)) >= self.view.get_cache_queue_size() \
                    and self.controller.get_content_flow(node, content, flow, log):
                self.controller.record_pkt_rejected(node, pkt_type, log)
            path = self.view.shortest_path(node, source)
            delay = self.view.link_delay(node, path[1])
            t_event = time + delay
            if node in self.cache_size:
                self.controller.add_probcache_c(flow)
                self.controller.add_probcache_N(flow, self.cache_size[node])
            self.controller.forward_request_hop_flow(node, path[1], flow, log)
            self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                       'content': content, 'node': path[1], 'flow': flow,
                                       'pkt_type': 'Request', 'log': log} )
        elif pkt_type == 'Data':
            if node == receiver:
                self.controller.end_flow_session_cache_delay(flow, log)
            else:
                path = self.view.shortest_path(node, receiver)
                source = self.view.content_source(content)
                path_to_source = self.view.shortest_path(node, source)
                if node in self.cache_size:
                    self.controller.add_probcache_x(flow)
                    # The (x/c) factor raised to the power of "c" according to the
                    # extended version of ProbCache published in IEEE TPDS
                    N = self.view.get_probcache_N(flow)
                    x = self.view.get_probcache_x(flow)
                    c = self.view.get_probcache_c(flow)
                    prob_cache = float(N) / (self.t_tw * self.cache_size[node]) * (x / c) ** c
                    i = random.random()
                    if i < prob_cache and len(self.view.cacheQ_node(node)) < self.view.get_cache_queue_size():
                        queue_delay = self.view.get_cache_queue_delay(node, time)
                        t_event = time + queue_delay
                        self.controller.cache_operation_flow(flow, queue_delay, log)
                        self.controller.add_cache_queue_event(node, {'t_event': t_event, 'receiver': receiver,
                                                                     'content': content, 'node': node, 'flow': flow,
                                                                     'pkt_type': 'put_content', 'log': log})
                        self.controller.report_cache_queue_size(node, pkt_type, log)
                        self.controller.record_pkt_admitted(node, pkt_type, log)
                        if path_to_source[1] in self.cache_size:
                            self.controller.subtract_probcache_N(flow, self.cache_size[path_to_source[1]])
                        return
                    elif i < prob_cache and len(self.view.cacheQ_node(node)) >= self.view.get_cache_queue_size():
                        self.controller.record_pkt_rejected(node, pkt_type, log)
                if path_to_source[1] in self.cache_size:
                    self.controller.subtract_probcache_N(flow, self.cache_size[path_to_source[1]])
                delay = self.view.link_delay(node, path[1])
                t_event = time + delay
                self.controller.forward_content_hop_flow(node, path[1], flow, log)
                self.controller.add_event( {'t_event': t_event, 'receiver': receiver,
                                            'content': content, 'node': path[1], 'flow': flow,
                                            'pkt_type': 'Data', 'log': log})
        elif pkt_type == 'get_content':
            # add the get operation
            path = self.view.shortest_path(node, receiver)
            delay = self.view.link_delay(node, path[1])
            t_event = time + delay
            self.controller.forward_content_hop_flow(node, path[1], flow, log)
            self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                        'content': content, 'node': path[1], 'flow': flow,
                                        'pkt_type': 'Data', 'log': log})
        elif pkt_type == 'put_content':
            # put content delay
            self.controller.put_content_flow(node, content, flow)
            path = self.view.shortest_path(node, receiver)
            delay = self.view.link_delay(node, path[1])
            t_event = time + delay
            self.controller.forward_content_hop_flow(node, path[1], flow, log)
            self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                        'content': content, 'node': path[1], 'flow': flow,
                                        'pkt_type': 'Data', 'log': log})
        else:
            raise ValueError('Invalid packet type')


@register_strategy('PROB_CACHE_AVOID_BUSY_NODE')
class ProbCachePacketLevelAvoidBusyNode(Strategy):
    """ProbCache strategy [3]_

    This strategy caches content objects probabilistically on a path with a
    probability depending on various factors, including distance from source
    and destination and caching space available on the path.

    This strategy was originally proposed in [2]_ and extended in [3]_. This
    class implements the extended version described in [3]_. In the extended
    version of ProbCache the :math`x/c` factor of the ProbCache equation is
    raised to the power of :math`c`.

    References
    ----------
    ..[2] I. Psaras, W. Chai, G. Pavlou, Probabilistic In-Network Caching for
          Information-Centric Networks, in Proc. of ACM SIGCOMM ICN '12
          Available: http://www.ee.ucl.ac.uk/~uceeips/prob-cache-icn-sigcomm12.pdf
    ..[3] I. Psaras, W. Chai, G. Pavlou, In-Network Cache Management and
          Resource Allocation for Information-Centric Networks, IEEE
          Transactions on Parallel and Distributerd Systems, 22 May 2014
          Available: http://doi.ieeecomputersociety.org/10.1109/TPDS.2013.304
    """

    @inheritdoc(Strategy)
    def __init__(self, view, controller, t_tw=2, a=1):
        super(ProbCachePacketLevelAvoidBusyNode, self).__init__(view, controller)
        self.t_tw = t_tw
        self.a = a
        self.cache_size = view.cache_nodes(size=True)

    @inheritdoc(Strategy)
    def process_event(self, time, receiver, content, node, flow, pkt_type, log):
        # get all required data
        # Route requests to original source and queries caches on the path
        source = self.view.content_source(content)
        if pkt_type == 'Request':
            if node == receiver:
                self.controller.start_flow_session(time, receiver, content, flow, log)
                self.controller.start_probcache_c(flow)
                self.controller.start_probcache_N(flow)
            elif (((node in self.cache_size) and len(self.view.cacheQ_node(node)) < self.view.get_cache_queue_size()) or node == source) \
                    and self.controller.get_content_flow(node, content, flow, log):
                if node in self.cache_size:
                    self.controller.add_probcache_c(flow)
                    self.controller.add_probcache_N(flow, self.cache_size[node])
                    # path = self.view.shortest_path(node, receiver)
                if node == source:
                    path = self.view.shortest_path(node, receiver)
                    delay = self.view.link_delay(node, path[1])
                    t_event = time + delay
                    self.controller.forward_content_hop_flow(node, path[1], flow, log)
                    self.controller.start_probcache_x(flow)
                    self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                               'content': content, 'node': path[1], 'flow': flow,
                                               'pkt_type': 'Data', 'log': log})
                else:
                    queue_delay = self.view.get_cache_queue_delay(node, time)
                    t_event = time + queue_delay
                    self.controller.cache_operation_flow(flow, queue_delay, log)
                    self.controller.start_probcache_x(flow)
                    self.controller.add_cache_queue_event(node, {'t_event': t_event, 'receiver': receiver,
                                                                 'content': content, 'node': node, 'flow': flow,
                                                                 'pkt_type': 'get_content', 'log': log})
                    self.controller.report_cache_queue_size(node, pkt_type, log)
                    self.controller.record_pkt_admitted(node, pkt_type, log)
                return
            elif (node in self.cache_size) and len(self.view.cacheQ_node(node)) >= self.view.get_cache_queue_size() \
                    and self.controller.get_content_flow(node, content, flow, log):
                self.controller.record_pkt_rejected(node, pkt_type, log)
                self.controller.track_busy_node(flow, node, log)
            path = self.view.shortest_path(node, source)
            delay = self.view.link_delay(node, path[1])
            t_event = time + delay
            if node in self.cache_size:
                self.controller.add_probcache_c(flow)
                self.controller.add_probcache_N(flow, self.cache_size[node])
            self.controller.forward_request_hop_flow(node, path[1], flow, log)
            self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                       'content': content, 'node': path[1], 'flow': flow,
                                       'pkt_type': 'Request', 'log': log} )
        elif pkt_type == 'Data':
            if node == receiver:
                self.controller.end_flow_session_cache_delay(flow, log)
            else:
                path = self.view.shortest_path(node, receiver)
                source = self.view.content_source(content)
                path_to_source = self.view.shortest_path(node, source)
                if node in self.cache_size:
                    self.controller.add_probcache_x(flow)
                    # The (x/c) factor raised to the power of "c" according to the
                    # extended version of ProbCache published in IEEE TPDS
                    N = self.view.get_probcache_N(flow)
                    x = self.view.get_probcache_x(flow)
                    c = self.view.get_probcache_c(flow)
                    queue_size_node = len(self.view.cacheQ_node(node))
                    if queue_size_node == 0:
                        queue_size_node = 1
                    inverse_queue_size_node = 1 / queue_size_node
                    sum_inverse_queue_size = 1
                    for queue in self.view.cacheQ():
                        queue_size = len(self.view.cacheQ_node(queue))
                        if queue_size == 0:
                            queue_size = 1
                        sum_inverse_queue_size += 1 / queue_size
                    i = random.random()
                    prob_cache = float(N) / (self.t_tw * self.cache_size[node]) * ((((c - x) / c) * inverse_queue_size_node / sum_inverse_queue_size) ** x) * ((x / c) ** (c - x))
                    if i < prob_cache and len(self.view.cacheQ_node(node)) < self.view.get_cache_queue_size() \
                            and (node not in self.view.track_busy_node(flow)):
                        queue_delay = self.view.get_cache_queue_delay(node, time)
                        t_event = time + queue_delay
                        self.controller.cache_operation_flow(flow, queue_delay, log)
                        self.controller.add_cache_queue_event(node, {'t_event': t_event, 'receiver': receiver,
                                                                     'content': content, 'node': node, 'flow': flow,
                                                                     'pkt_type': 'put_content', 'log': log})
                        self.controller.report_cache_queue_size(node, pkt_type, log)
                        self.controller.record_pkt_admitted(node, pkt_type, log)
                        if path_to_source[1] in self.cache_size:
                            self.controller.subtract_probcache_N(flow, self.cache_size[path_to_source[1]])
                        return
                    elif i < prob_cache \
                            and (len(self.view.cacheQ_node(node)) >= self.view.get_cache_queue_size() or node in self.view.track_busy_node(flow)):
                        self.controller.record_pkt_rejected(node, pkt_type, log)
                if path_to_source[1] in self.cache_size:
                    self.controller.subtract_probcache_N(flow, self.cache_size[path_to_source[1]])
                delay = self.view.link_delay(node, path[1])
                t_event = time + delay
                self.controller.forward_content_hop_flow(node, path[1], flow, log)
                self.controller.add_event( {'t_event': t_event, 'receiver': receiver,
                                            'content': content, 'node': path[1], 'flow': flow,
                                            'pkt_type': 'Data', 'log': log})
        elif pkt_type == 'get_content':
            # add the get operation
            path = self.view.shortest_path(node, receiver)
            delay = self.view.link_delay(node, path[1])
            t_event = time + delay
            self.controller.forward_content_hop_flow(node, path[1], flow, log)
            self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                        'content': content, 'node': path[1], 'flow': flow,
                                        'pkt_type': 'Data', 'log': log})
        elif pkt_type == 'put_content':
            # put content delay
            self.controller.put_content_flow(node, content, flow)
            path = self.view.shortest_path(node, receiver)
            delay = self.view.link_delay(node, path[1])
            t_event = time + delay
            self.controller.forward_content_hop_flow(node, path[1], flow, log)
            self.controller.add_event({'t_event': t_event, 'receiver': receiver,
                                        'content': content, 'node': path[1], 'flow': flow,
                                        'pkt_type': 'Data', 'log': log})
        else:
            raise ValueError('Invalid packet type')


@register_strategy('CL4M')
class CacheLessForMore(Strategy):
    """Cache less for more strategy [4]_.

    This strategy caches items only once in the delivery path, precisely in the
    node with the greatest betweenness centrality (i.e., that is traversed by
    the greatest number of shortest paths). If the argument *use_ego_betw* is
    set to *True* then the betweenness centrality of the ego-network is used
    instead.

    References
    ----------
    ..[4] W. Chai, D. He, I. Psaras, G. Pavlou, Cache Less for More in
          Information-centric Networks, in IFIP NETWORKING '12
          Available: http://www.ee.ucl.ac.uk/~uceeips/centrality-networking12.pdf
    """

    @inheritdoc(Strategy)
    def __init__(self, view, controller, use_ego_betw=False, **kwargs):
        super(CacheLessForMore, self).__init__(view, controller)
        topology = view.topology()
        if use_ego_betw:
            self.betw = dict((v, nx.betweenness_centrality(nx.ego_graph(topology, v))[v])
                             for v in topology.nodes())
        else:
            self.betw = nx.betweenness_centrality(topology)

    @inheritdoc(Strategy)
    def process_event(self, time, receiver, content, log):
        # get all required data
        source = self.view.content_source(content)
        path = self.view.shortest_path(receiver, source)
        # Route requests to original source and queries caches on the path
        self.controller.start_session(time, receiver, content, log)
        for u, v in path_links(path):
            self.controller.forward_request_hop(u, v)
            if self.view.has_cache(v):
                if self.controller.get_content(v):
                    serving_node = v
                    break
        # No cache hits, get content from source
        else:
            self.controller.get_content(v)
            serving_node = v
        # Return content
        path = list(reversed(self.view.shortest_path(receiver, serving_node)))
        # get the cache with maximum betweenness centrality
        # if there are more than one cache with max betw then pick the one
        # closer to the receiver
        max_betw = -1
        designated_cache = None
        for v in path[1:]:
            if self.view.has_cache(v):
                if self.betw[v] >= max_betw:
                    max_betw = self.betw[v]
                    designated_cache = v
        # Forward content
        for u, v in path_links(path):
            self.controller.forward_content_hop(u, v)
            if v == designated_cache:
                self.controller.put_content(v)
        self.controller.end_session()


@register_strategy('RAND_BERNOULLI')
class RandomBernoulli(Strategy):
    """Bernoulli random cache insertion.

    In this strategy, a content is randomly inserted in a cache on the path
    from serving node to receiver with probability *p*.
    """

    @inheritdoc(Strategy)
    def __init__(self, view, controller, p=0.2, **kwargs):
        super(RandomBernoulli, self).__init__(view, controller)
        self.p = p

    @inheritdoc(Strategy)
    def process_event(self, time, receiver, content, log):
        # get all required data
        source = self.view.content_source(content)
        path = self.view.shortest_path(receiver, source)
        # Route requests to original source and queries caches on the path
        self.controller.start_session(time, receiver, content, log)
        for u, v in path_links(path):
            self.controller.forward_request_hop(u, v)
            if self.view.has_cache(v):
                if self.controller.get_content(v):
                    serving_node = v
                    break
        else:
            # No cache hits, get content from source
            self.controller.get_content(v)
            serving_node = v
        # Return content
        path = list(reversed(self.view.shortest_path(receiver, serving_node)))
        for u, v in path_links(path):
            self.controller.forward_content_hop(u, v)
            if v != receiver and self.view.has_cache(v):
                if random.random() < self.p:
                    self.controller.put_content(v)
        self.controller.end_session()


@register_strategy('RAND_CHOICE')
class RandomChoice(Strategy):
    """Random choice strategy

    This strategy stores the served content exactly in one single cache on the
    path from serving node to receiver selected randomly.
    """

    @inheritdoc(Strategy)
    def __init__(self, view, controller, **kwargs):
        super(RandomChoice, self).__init__(view, controller)

    @inheritdoc(Strategy)
    def process_event(self, time, receiver, content, log):
        # get all required data
        source = self.view.content_source(content)
        path = self.view.shortest_path(receiver, source)
        # Route requests to original source and queries caches on the path
        self.controller.start_session(time, receiver, content, log)
        for u, v in path_links(path):
            self.controller.forward_request_hop(u, v)
            if self.view.has_cache(v):
                if self.controller.get_content(v):
                    serving_node = v
                    break
        else:
            # No cache hits, get content from source
            self.controller.get_content(v)
            serving_node = v
        # Return content
        path = list(reversed(self.view.shortest_path(receiver, serving_node)))
        caches = [v for v in path[1:-1] if self.view.has_cache(v)]
        designated_cache = random.choice(caches) if len(caches) > 0 else None
        for u, v in path_links(path):
            self.controller.forward_content_hop(u, v)
            if v == designated_cache:
                self.controller.put_content(v)
        self.controller.end_session()
