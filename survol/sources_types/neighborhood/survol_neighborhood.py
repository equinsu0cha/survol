#!/usr/bin/python

"""
Neighboring Survol agents.
"""

import sys
import lib_util
import lib_common
import lib_credentials

def AddSurvolNode(grph,hostSurvol,urlSurvolClean):
	sys.stderr.write("AddSurvolNode hostSurvol=%s\n"%(hostSurvol))
	survolHostNode = lib_common.gUriGen.HostnameUri( hostSurvol )

	currDispMode = lib_util.GuessDisplayMode()

	# Several possibilities:
	# - Open a new HTML page with this URL. Or SVG, passed on the current mode.
	# - If we are in D3 mode, this should return a JSON object from the other agent.
	if currDispMode == "json":

		if lib_util.IsLocalAddress( hostSurvol ):
			machName_or_None = None
			serverBox = lib_common.gUriGen
		else:
			machName_or_None = hostSurvol
			serverBox = lib_common.OtherAgentBox(urlSurvolClean)

		# This is the URL of the remote host, on the remote agent.
		nodeRemoteHost = serverBox.HostnameUri(hostSurvol)
		grph.add( ( survolHostNode, lib_common.MakeProp("Survol host"), nodeRemoteHost ) )

		grph.add( ( survolHostNode, lib_common.MakeProp("Survol agent"), lib_common.NodeUrl(urlSurvolClean) ) )

	else:
		urlSurvolModed = lib_util.AnyUriModed(urlSurvolClean, currDispMode)

		# Should check the URL to be sure it is valid.

		# sys.stderr.write("AddSurvolNode urlSurvolModed=%s\n"%(urlSurvolModed))
		grph.add( ( survolHostNode, lib_common.MakeProp("Survol agent"), lib_common.NodeUrl(urlSurvolModed) ) )


def SurvolServersDisplay(grph):
	lstSurvolServers = []
	credNames = lib_credentials.GetCredentialsNames( "Survol" )
	sys.stderr.write("SurvolServersDisplay\n")
	for urlSurvol in credNames:
		# sys.stderr.write("SurvolServersDisplay urlSurvol=%s\n"%(urlSurvol))

		# Same when returning from WbemServersList.
		# urlSurvolClean = lib_credentials.KeyUrlCgiEncode(urlSurvol)
		urlSurvolClean = urlSurvol
		# sys.stderr.write("SurvolServersDisplay urlSurvolClean=%s\n"%(urlSurvolClean))

		# The credentials are not needed until a Survol agent uses HTTPS.
		parsed_url = lib_util.survol_urlparse( urlSurvol )
		hostSurvol = parsed_url.hostname
		# sys.stderr.write("SurvolServersDisplay hostSurvol=%s\n"%(hostSurvol))
		if not hostSurvol:
			continue

		AddSurvolNode(grph,hostSurvol,urlSurvolClean)



def Main():

	cgiEnv = lib_common.CgiEnv()

	grph = cgiEnv.GetGraph()

	SurvolServersDisplay(grph)

	cgiEnv.OutCgiRdf()


if __name__ == '__main__':
	Main()
