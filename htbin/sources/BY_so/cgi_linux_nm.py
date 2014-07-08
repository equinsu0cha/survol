#!/usr/bin/python

import os
import sys
import psutil
import socket
import urllib
import cgi        # One of the CGI arguments is the name of the shared library.

import rdflib
from rdflib import Literal

import lib_common
from lib_common import pc

def DoNothing():
	return

def AddKnown(symbol):
	symbolNode = lib_common.SymbolUri( symbol )
	grph.add( ( nodeSharedLib, pc.property_symbol_defined, symbolNode ) )

def AddUnknown(symbol):
	symbolNode = lib_common.SymbolUri( symbol )
	grph.add( ( nodeSharedLib, pc.property_symbol_undefined, symbolNode ) )


grph = rdflib.Graph()

# This can be run from the command line like this:
# QUERY_STRING="SHAREDLIB=/usr/lib/libkdecore.so" htbin/sources/cgi_linux_nm.py
# The url must be encoded at this stage.

arguments = cgi.FieldStorage()
try:
	fileSharedLib = arguments["entity_id"].value
except KeyError:
	lib_common.ErrorMessageHtml("Must provide an shared library")

nodeSharedLib = lib_common.FileUri( fileSharedLib )

stream = os.popen("nm -DC " + fileSharedLib)

# Just to have a sort of clean switch.

# 0001d75c A __bss_start
#         U __cxa_allocate_exception

for line in stream:
	type = line[9].upper()
	tail = urllib.quote( line[11:-1] )

	if 0:
		DoNothing()
        #"A" The symbol's value is absolute, and will not be changed by further linking.
        #"B"
        #"b" The symbol is in the uninitialized data section (known as BSS).
        #"C" The symbol is common.  Common symbols are uninitialized data.  When linking, multiple common
        #    symbols may appear with the same name.  If the symbol is defined anywhere, the common symbols
        #    are treated as undefined references.
        #"D"
        #"d" The symbol is in the initialized data section.
        #"G"
        #"g" The symbol is in an initialized data section for small objects.  Some object file formats
        #    permit more efficient access to small data objects, such as a global int variable as opposed to
        #    a large global array.
        #"I" The symbol is an indirect reference to another symbol.  This is a GNU extension to the a.out
        #    object file format which is rarely used.
        #"i" The symbol is in a section specific to the implementation of DLLs.
        #"N" The symbol is a debugging symbol.
        #"p" The symbols is in a stack unwind section.
        #"R"
        #"r" The symbol is in a read only data section.
        #"S"
        #"s" The symbol is in an uninitialized data section for small objects.
        #"T"
        #"t" The symbol is in the text (code) section.
	elif type == 'T' or type == 't':
		AddKnown( tail )
        #"U" The symbol is undefined.
	elif type == 'U' :
		AddUnknown( tail )
        #"V"
        #"v" The symbol is a weak object.  When a weak defined symbol is linked with a normal defined
        #    symbol, the normal defined symbol is used with no error.  When a weak undefined symbol is
        #    linked and the symbol is not defined, the value of the weak symbol becomes zero with no erro
        #    On some systems, uppercase indicates that a default value has been specified.
        #"W"
        #"w" The symbol is a weak symbol that has not been specifically tagged as a weak object symbol.
        #    When a weak defined symbol is linked with a normal defined symbol, the normal defined symbol is
        #    used with no error.  When a weak undefined symbol is linked and the symbol is not defined, the
        #    value of the symbol is determined in a system-specific manner without error.  On some systems,
        #    uppercase indicates that a default value has been specified.
        #"-" The symbol is a stabs symbol in an a.out object file.  In this case, the next values printed
        #    are the stabs other field, the stabs desc field, and the stab type.  Stabs symbols are used to
        #    hold debugging information.
        #"?" The symbol type is unknown, or object file format specific.
	else:
		DoNothing()
lib_common.OutCgiRdf(grph)


