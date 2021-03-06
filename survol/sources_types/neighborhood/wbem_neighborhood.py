#!/usr/bin/env python

"""
Neighboring WBEM agents.
"""

import sys
import logging
import lib_util
import lib_wbem
import lib_common
import lib_credentials
from lib_properties import pc
from sources_types import neighborhood as survol_neighborhood


# Similar to portal_wbem.py except that:
# - This script uses SLP.
# - This script can only give top-level URLs.


def AddFromWbemCimom(grph,cimomWbem):
	parsed_url = lib_util.survol_urlparse( cimomWbem )
	hostWbem = parsed_url.hostname
	logging.debug("WbemServersDisplay hostWbem=%s",hostWbem)
	if not hostWbem:
		return None

	# http://rchateau-hp:8000/survol/namespaces_wbem.py?xid=http:%2F%2F192.168.0.17:5988/.
	cimomWbemCgi = cimomWbem.replace("//","%2f%2f")
	logging.debug("cimomWbem=%s cimomWbemCgi=%s",cimomWbem,cimomWbemCgi)

	urlWbem = lib_wbem.WbemAllNamespacesUrl(cimomWbemCgi)
	wbemNode = lib_common.NodeUrl(urlWbem)

	wbemHostNode = lib_common.gUriGen.HostnameUri( hostWbem )

	grph.add(( wbemNode, pc.property_information, lib_util.NodeLiteral(cimomWbem) ) )
	grph.add(( wbemNode, pc.property_host, wbemHostNode ) )

	return wbemNode


def WbemServersDisplay(grph):
	lstWbemServers = []
	credNames = lib_credentials.get_credentials_names( "WBEM" )
	logging.debug("WbemServersDisplay")
	for cimomWbem in credNames:
		logging.debug("WbemServersDisplay cimomWbem=%s",cimomWbem)

		# The credentials are not needed until a Survol agent uses HTTPS.

		wbemNode = AddFromWbemCimom(grph,cimomWbem)
		if not wbemNode:
			continue
		grph.add(( wbemNode, pc.property_information, lib_util.NodeLiteral("Static definition") ) )


def Main():
	# If this flag is set, the script uses SLP to discover WBEM Agents.
	paramkeySLP = "Service Location Protocol"

	cgiEnv = lib_common.CgiEnv(
		parameters = { paramkeySLP : False }
	)

	flagSLP = bool(cgiEnv.get_parameters( paramkeySLP ))

	grph = cgiEnv.GetGraph()

	WbemServersDisplay(grph)

	if flagSLP:
		dictServices = survol_neighborhood.GetSLPServices("survol")
		for keyService in dictServices:
			wbemNode = AddFromWbemCimom(grph,keyService)

			if not wbemNode:
				continue

			grph.add(( wbemNode, pc.property_information, lib_util.NodeLiteral("Service Location Protocol") ) )

			attrsService = dictServices[keyService]
			for keyAttr in attrsService:
				propAttr = lib_common.MakeProp(keyAttr)
				valAttr = attrsService[keyAttr]
				grph.add( ( wbemNode, propAttr, lib_util.NodeLiteral(valAttr) ) )

	cgiEnv.OutCgiRdf()


if __name__ == '__main__':
	Main()
