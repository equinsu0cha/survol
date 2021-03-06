#!/usr/bin/env python

"""
Information about an Azure service
"""

import sys
import socket
import logging
import lib_util
import lib_common
from lib_properties import pc
import lib_credentials
from azure import *
from azure.servicemanagement import *

from sources_types import Azure
from sources_types.Azure import subscription
from sources_types.Azure import location
from sources_types.Azure import service

Usable = lib_util.UsableWindows

def Main():
	cgiEnv = lib_common.CgiEnv()

	# TODO: The subscription will become a parameter with a default value.
	# serviceName = cgiEnv.GetId()
	serviceName = cgiEnv.m_entity_id_dict["Id"]

	# subscriptionName=Azure.DefaultSubscription()
	subscriptionName = cgiEnv.m_entity_id_dict["Subscription"]

	grph = cgiEnv.GetGraph()

	(subscription_id,certificate_path) = lib_credentials.GetCredentials( "Azure", subscriptionName )

	sms = ServiceManagementService(subscription_id, certificate_path)

	subscriptionNode = subscription.MakeUri( subscriptionName )

	srv = sms.get_hosted_service_properties(serviceName)

	logging.debug("srv=%s", str(dir(srv)))
	logging.debug("deployments=%s",str(srv.deployments))
	logging.debug("srv.hosted_service_properties=%s", str(dir(srv.hosted_service_properties)))
	logging.debug("srv.hosted_service_properties.extended_properties=%s", str(dir(srv.hosted_service_properties.extended_properties)))

	servNode = service.MakeUri( srv.service_name, subscriptionName )
	grph.add( ( subscriptionNode, lib_common.MakeProp("Service"), servNode ) )

	locaNode = location.MakeUri( srv.hosted_service_properties.location, subscriptionName )
	grph.add( ( servNode, lib_common.MakeProp("Location"), locaNode ) )

	grph.add( ( servNode, pc.property_rdf_data_nolist1, lib_common.NodeUrl(srv.url) ) )

	grph.add( ( servNode, lib_common.MakeProp("deployments"), lib_util.NodeLiteral(str(srv.deployments) ) ) )

	# With a dot ".", they come first.
	grph.add( ( servNode, lib_common.MakeProp(".affinity_group"), lib_util.NodeLiteral(srv.hosted_service_properties.affinity_group ) ) )
	grph.add( ( servNode, lib_common.MakeProp(".date_created"), lib_util.NodeLiteral(srv.hosted_service_properties.date_created ) ) )
	grph.add( ( servNode, lib_common.MakeProp(".date_last_modified"), lib_util.NodeLiteral(srv.hosted_service_properties.date_last_modified ) ) )
	grph.add( ( servNode, lib_common.MakeProp(".description"), lib_util.NodeLiteral(srv.hosted_service_properties.description ) ) )
	grph.add( ( servNode, lib_common.MakeProp(".label"), lib_util.NodeLiteral(srv.hosted_service_properties.label ) ) )
	grph.add( ( servNode, lib_common.MakeProp(".status"), lib_util.NodeLiteral(srv.hosted_service_properties.status ) ) )

	for extProp in srv.hosted_service_properties.extended_properties:
		extVal = srv.hosted_service_properties.extended_properties[ extProp ]
		grph.add( ( servNode, lib_common.MakeProp(extProp), lib_util.NodeLiteral(extVal) ) )


	cgiEnv.OutCgiRdf()

if __name__ == '__main__':
	Main()

