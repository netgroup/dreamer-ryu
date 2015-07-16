# Copyright (C) 2013 Nippon Telegraph and Telephone Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
from webob import Response
import networkx as nx
from random import randrange


from ryu.app.wsgi import ControllerBase, WSGIApplication, route
from ryu.base import app_manager
from ryu.lib import dpid as dpid_lib
from ryu.lib import port_no as port_no_lib
from ryu.topology.api import get_switch, get_link

# REST API for switch configuration
#
# get all the switches
# GET /v1.0/topology/switches
#
# get the switch
# GET /v1.0/topology/switches/<dpid>
#
# get all the links
# GET /v1.0/topology/links
#
# get the links of a switch
# GET /v1.0/topology/links/<dpid>
#
# XXX
# get the route that interconnects input switches
# GET /v1.0/topology/route/<srcdpid>/<srcport>/<dstdpid>/<dstport>
#
# where
# <dpid>: datapath id in 16 hex


class TopologyAPI(app_manager.RyuApp):
    _CONTEXTS = {
        'wsgi': WSGIApplication
    }

    def __init__(self, *args, **kwargs):
        super(TopologyAPI, self).__init__(*args, **kwargs)

        wsgi = kwargs['wsgi']
        wsgi.register(TopologyController, {'topology_api_app': self})


class TopologyController(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(TopologyController, self).__init__(req, link, data, **config)
        self.topology_api_app = data['topology_api_app']

    @route('topology', '/v1.0/topology/switches',
           methods=['GET'])
    def list_switches(self, req, **kwargs):
        return self._switches(req, **kwargs)

    @route('topology', '/v1.0/topology/switches/{dpid}',
           methods=['GET'], requirements={'dpid': dpid_lib.DPID_PATTERN})
    def get_switch(self, req, **kwargs):
        return self._switches(req, **kwargs)

    @route('topology', '/v1.0/topology/links',
           methods=['GET'])
    def list_links(self, req, **kwargs):
        return self._links(req, **kwargs)

    @route('topology', '/v1.0/topology/links/{dpid}',
           methods=['GET'], requirements={'dpid': dpid_lib.DPID_PATTERN})
    def get_links(self, req, **kwargs):
        return self._links(req, **kwargs)

    @route('topology', '/v1.0/topology/route/{srcdpid}/{srcport}/{dstdpid}/{dstport}',
           methods=['GET'], requirements={'srcdpid': dpid_lib.DPID_PATTERN,
          'srcport': port_no_lib.PORT_NO_PATTERN, 'dstdpid': dpid_lib.DPID_PATTERN,
          'dstport': port_no_lib.PORT_NO_PATTERN})
    def get_route(self, req, **kwargs):
        return self._route(req, **kwargs)

    def _switches(self, req, **kwargs):
        dpid = None
        if 'dpid' in kwargs:
            dpid = dpid_lib.str_to_dpid(kwargs['dpid'])
        switches = get_switch(self.topology_api_app, dpid)
        body = json.dumps([switch.to_dict() for switch in switches])
        return Response(content_type='application/json', body=body)

    def _links(self, req, **kwargs):
        dpid = None
        if 'dpid' in kwargs:
            dpid = dpid_lib.str_to_dpid(kwargs['dpid'])
        links = get_link(self.topology_api_app, dpid)
        body = json.dumps([link.to_dict() for link in links])
        return Response(content_type='application/json', body=body)

    def _route(self, req, **kwargs):
        srcdpid=dpid_lib.str_to_dpid(kwargs['srcdpid'])
        srcport=port_no_lib.str_to_port_no(kwargs['srcport'])
        dstdpid=dpid_lib.str_to_dpid(kwargs['dstdpid'])
        dstport=port_no_lib.str_to_port_no(kwargs['dstport'])
        links = get_link(self.topology_api_app, None)
        
        topology = nx.MultiDiGraph()
        for link in links:
            print link
            topology.add_edge(link.src.dpid, link.dst.dpid, src_port=link.src.port_no, dst_port=link.dst.port_no)
        
        try:    
            shortest_path = nx.shortest_path(topology, srcdpid, dstdpid)
        except (nx.NetworkXError, nx.NetworkXNoPath):
            body = json.dumps([])
            print "Error"
            return Response(content_type='application/json', body=body)
            
        ingressPort = NodePortTuple(srcdpid, srcport)
        egressPort = NodePortTuple(dstdpid, dstport)
        route = []
        route.append(ingressPort)
        
        for i in range(0, len(shortest_path)-1):
            link = topology[shortest_path[i]][shortest_path[i+1]]
            index = randrange(len(link))
            dstPort = NodePortTuple(shortest_path[i], link[index]['src_port'])
            srcPort = NodePortTuple(shortest_path[i+1], link[index]['dst_port'])
            route.append(dstPort)
            route.append(srcPort)
            
        route.append(egressPort)
        body = json.dumps([hop.to_dict() for hop in route])
        return Response(content_type='application/json', body=body)
        
        
class NodePortTuple(object):
    
    def __init__(self, dpid, port_no):
        self.dpid = dpid_lib.dpid_to_str(dpid)
        self.port_no = port_no_lib.port_no_to_str(port_no)
        
    def to_dict(self):
        return {'switch': self.dpid, 'port':self.port_no}
        
    def __str__(self):
        return 'NodePortTuple<switch=%s, port=%s>' % (self.dpid, self.port_no)
