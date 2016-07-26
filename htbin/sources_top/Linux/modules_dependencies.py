#!/usr/bin/python

"""
Linux modules dependencies
"""

import lib_common
import lib_util
import sys
import psutil
import socket
import rdflib
from lib_properties import pc

Usable = lib_util.UsableLinux

#
# The modules.dep as generated by module-init-tools depmod,
# lists the dependencies for every module in the directories
# under /lib/modules/version, where modules.dep is. 
#
# cat /proc/version
# Linux version 2.6.24.7-desktop586-2mnb (qateam@titan.mandriva.com) (gcc version 4.2.3 (4.2.3-6mnb1)) #1 SMP Thu Oct 30 17:39:28 EDT 2008
# ls /lib/modules/$(cat /proc/version | cut -d " " -f3)/modules.dep
#
# /lib/modules/2.6.24.7-desktop586-2mnb/modules.dep
# /lib/modules/2.6.24.7-desktop586-2mnb/dkms-binary/drivers/char/hsfmc97via.ko.gz: /lib/modules/2.6.24.7-desktop586-2mnb/dkms-binary/drivers/char/hsfserial.ko.gz /lib/modules/2.6.24.7-desktop586-2mnb/dkms-binary/drivers/char/hsfengine.ko.gz /lib/modules/2.6.24.7-desktop586-2mnb/dkms-binary/drivers/char/hsfosspec.ko.gz /lib/modules/2.6.24.7-desktop586-2mnb/kernel/drivers/usb/core/usbcore.ko.gz /lib/modules/2.6.24.7-desktop586-2mnb/dkms-binary/drivers/char/hsfsoar.ko.gz
#
#




def Main():
	cgiEnv = lib_common.CgiEnv()

	if not lib_util.isPlatformLinux:
		lib_common.ErrorMessageHtml("Modules dependencies for Linux only")

	grph = rdflib.Graph()

	# This can work on Linux only.
	version_file = open("/proc/version","r")
	version_line = version_file.read()
	version = version_line.split(' ')[2]

	Main.DictModules = dict()

	def ModuleToNode(modnam):
		try:
			return Main.DictModules[modnam]
		except KeyError:
			nod = lib_common.gUriGen.FileUri(modnam)
			Main.DictModules[modnam] = nod
			return nod


	# The dependency network is very messy, so we put a limit,
	# for the moment.
	maxCnt=0

	module_deps_name = "/lib/modules/" + version + "/modules.dep"
	modules_file = open(module_deps_name,"r")
	for modules_line in modules_file:
		modules_split_colon = modules_line.split(':')
		module_name = modules_split_colon[0]
		module_deps_list = modules_split_colon[1].split(' ')

		# NOT TOO MUCH NODES: BEYOND THIS, IT IS FAR TOO SLOW, UNUSABLE.
		# HARDCODE_LIMIT
		maxCnt += 1
		if maxCnt > 2000:
			break

		file_parent = ModuleToNode(module_name)
		file_child = None
		for module_dep in module_deps_list:
			module_dep = module_dep.strip()
			if module_dep == "":
				continue

			# print ( module_name + " => " + module_dep )

			# This generates a directed acyclic graph,
			# but not a tree in the general case.
			file_child = ModuleToNode(module_dep)

			grph.add( ( file_parent, pc.property_module_dep, file_child ) )
		# TODO: Ugly trick, otherwise nodes without connections are not displayed.
		# TODO: I think this is a BUG in the dot file generation. Or in RDF ?...
		if file_child is None:
			grph.add( ( file_parent, pc.property_information, rdflib.Literal("") ) )

	# Splines are rather slow.
	if maxCnt > 100:
		layoutType = "LAYOUT_XXX"
	else:
		layoutType = "LAYOUT_SPLINE"
	cgiEnv.OutCgiRdf(grph, layoutType)

if __name__ == '__main__':
	Main()
