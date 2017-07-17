import lib_properties
import lib_patterns
import lib_naming
import lib_util
import rdflib
from lib_properties import pc
import sys
import time
import cgi
import re
import os
import json
import six

from six.moves.html_parser import HTMLParser

try:
	from urlparse import urlparse
except ImportError:
	from urllib.parse import urlparse


# "http://primhillcomputers.com/ontologies/smbshare" = > "smbshare"
def AntiPredicateUri(uri):
	return uri[ len(lib_properties.primns_slash) : ]

################################################################################

# Current URL but in edition mode.
# PROBLEM: SI PAS DE ENTITY_ID A EDITER CAR "TOP" ALORS ON REBOUCLE SUR Edit:
# DONC DETECTER LE TYPE DE L'ENTITE EN FOCNTION DU DIRECTORY ET AUCUN SI "TOP".
def ModedUrl(otherMode):
	return lib_util.RequestUriModed(otherMode)

################################################################################
def TruncateInSpace(labText,maxLenLab):
	if len( labText ) > maxLenLab:
		idx = labText.find(" ",maxLenLab)
		# sys.stderr.write("idx=%d\n"%idx)
		if idx < 0:
			idx = maxLenLab

			# BEWARE: This must not fall in the middle of an html entity "&amp;", etc... ...
			idxSemiColon = labText.find(";",idx)
			# sys.stderr.write("idxSemiColon=%d\n"%idxSemiColon)
			if idxSemiColon < 0:
				idx = maxLenLab
			else:
				idx = idxSemiColon + 1 # Just after the semi-colon.

		# sys.stderr.write("labText=%s idx=%d\n"%(labText,idx))
		return labText[:idx]
	else:
		return labText

################################################################################

maxHtmlTitleLenPerCol = 40
withBrDelim = '<BR ALIGN="LEFT" />'

# Inserts "<BR/>" in a HTML string so it is wrapped in a HTML label.
def StrWithBr(str, colspan = 1):
	lenStr = len(str)
	maxHtmlTitleLen = colspan * maxHtmlTitleLenPerCol
	if lenStr < maxHtmlTitleLen:
		return str

	splt = str.split(" ")
	totLen = 0
	resu = ""
	currLine = ""
	for currStr in splt:
		subLen = len(currStr)
		if totLen + subLen < maxHtmlTitleLen:
			currLine += " " + currStr
			totLen += subLen
			continue
		if resu:
			resu += withBrDelim
		resu += currLine
		currLine = currStr
		totLen = subLen

	if currLine:
		if resu != "":
			resu += withBrDelim
		resu += currLine
	return resu

################################################################################

# TODO: Set the right criteria for an old Graphviz version.
new_graphiz = True # sys.version_info >= (3,)

# TODO: This is temporary because only old graphviz versions dot not implement that.
def DotBold(str):
	return "<b>%s</b>" % str if new_graphiz else str

def DotUL(str):
	return "<u>%s</u>" % str if new_graphiz else str

def DotIt(str):
	return "<i>%s</i>" % str if new_graphiz else str

################################################################################

from lib_util import WrtAsUtf
from lib_util import WrtHeader

################################################################################

# Transforms a RDF graph into a HTML page.
def Grph2Html( page_title, error_msg, isSubServer, parameters, grph):
	# TODO: Est-ce necessaire d'utiliser WrtAsUtf au lieu de print() ?
	# Peut-etre oui, a cause des sockets?
	WrtHeader('text/html')
	# WrtAsUtf( "Content-type: text/html\n\n<head>" )
	WrtAsUtf( "<head>" )

	# TODO: Encode the HTML special characters.
	WrtAsUtf( "<title>" + page_title + "</title>")

	# TODO: Essayer de rassembler les literaux relatifs au memes noeuds, pour faire une belle presentation.

	WrtAsUtf( ' </head> <body>')

	WrtAsUtf('<table border="1">')

	WrtAsUtf('<tr><td colspan="3"><a href="' + ModedUrl("edit") + '">CGI parameters edition</a></td></tr>')

	for keyParam,valParam in parameters.items():
		WrtAsUtf('<tr><td>' + keyParam + '</td><td colspan="2">' + valParam + '</td></tr>')

	WrtAsUtf('<tr><td colspan="3"><a href="' + ModedUrl("svg") + '">Content as SVG</a></td></tr>')
	WrtAsUtf('<tr><td colspan="3"><a href="' + ModedUrl("rdf") + '">Content as RDF</a></td></tr>')
	WrtAsUtf('<tr><td colspan="3">' + str(len(grph)) + ' nodes</td></tr>')

	if error_msg != None:
		WrtAsUtf('<tr><td colspan="3"><b>' + error_msg + '</b></td></tr>')

	if isSubServer:
		WrtAsUtf('<tr><td colspan="3"><a href="' + ModedUrl("stop") + '">Stop subserver</a></td></tr>')

	by_subj = dict()
	for subj, pred, obj in grph:
		# No point displaying some keys if there is no value.
		if pred == pc.property_information :
			if str(obj) == "":
				continue

		the_tup = ( pred, obj )
		try:
			by_subj[ subj ].append( the_tup )
		except KeyError:
			by_subj[ subj ] = [ the_tup ]

	for subj, the_tup_list in list( by_subj.items() ):

		subj_str = str(subj)
		subj_title = lib_naming.ParseEntityUri(subj_str)[0]

		cnt_rows = len( the_tup_list )

		mustWriteColOne = True

		for pred, obj in the_tup_list:
			WrtAsUtf( "<tr>" )

			if mustWriteColOne:
				WrtAsUtf( '<td rowspan="' + str(cnt_rows) + '"><a href="' + subj_str + '">'+ subj_title +"</a></td>")
				mustWriteColOne = False

			obj_str = str(obj)

			if isinstance( obj , (rdflib.URIRef, rdflib.BNode)):
				obj_title = lib_naming.ParseEntityUri(obj_str)[0]
				WrtAsUtf( "<td>" + AntiPredicateUri(str(pred)) + "</td>")
				url_with_mode = lib_util.ConcatenateCgi( obj_str, "mode=html" )
				WrtAsUtf( '<td><a href="' + url_with_mode + '">' + obj_title + "</a></td>")
			else:
				if pred == pc.property_information :
					WrtAsUtf( '<td colspan="2">' + obj_str + "</td>")
				else:
					WrtAsUtf( '<td>' + AntiPredicateUri(str(pred)) + "</td>")
					WrtAsUtf( '<td>' + obj_str + "</td>")

			WrtAsUtf( "</tr>")

	WrtAsUtf( " </table> </body> </html> ")

################################################################################

# def Graphic_shape():
# 	return "egg"
#
# def Graphic_colorfill():
# 	return "#CCCC33"
#
# def Graphic_colorbg():
# 	return "#CCCC33"
#
# def Graphic_border():
# 	return 0
#
# def Graphic_is_rounded():
# 	return True

#		arrayGraphParams = TypeToGraphParams(type)

NodeJsonNumber = 0

# This models a node as it will be saved to Json.
class NodeJson:
	def __init__(self,rdf_node):
		global NodeJsonNumber
		subj_str = str(rdf_node)

		( entity_label, entity_graphic_class, entity_id ) = lib_naming.ParseEntityUri(subj_str)

		self.m_label = entity_label.strip()
		self.m_class = entity_graphic_class

		arrayGraphParams = lib_patterns.TypeToGraphParams(self.m_class)

		# "Graphic_shape","Graphic_colorfill","Graphic_colorbg","Graphic_border","Graphic_is_rounded"
		self.m_color = arrayGraphParams[1]


		# TODO: Display the doc in the module with FromModuleToDoc(importedMod,filDfltText):
		self.m_info_list = [entity_graphic_class]
		self.m_info_dict = dict()
		self.m_index = NodeJsonNumber
		NodeJsonNumber += 1 # One more node.

# Transforms a RDF property name into a pure alphanum string usable as a DOT label.
def PropToShortPropNam(collapsProp):
	shortNam = collapsProp.split("/")[-1]
	# "sun.boot.class.path"
	# Graphviz just want letters.
	shortNam = shortNam.replace(".","_")
	shortNam = shortNam.replace(" ","_")
	return shortNam

# Only some scripts are exported to Json.
def ScriptForJson(url):
	# The only internal script accepted.
	if( url.find("htbin/entity.py") >= 0):
		return True

	# TODO: Maybe pass portal_wbem.py and portal_wmi.py ??

	# Other scripts are forbidden.
	if( url.find("htbin/") >= 0):
		return False

	# Foreign scripts are OK.
	return True

# Transforms a RDF graph into a JSON document.
# This returns a graph made of Json objects.
def Grph2Json(page_title, error_msg, isSubServer, parameters, grph):

	# It contains a cache because the same nodes may appear several times.
	def NodeToJsonObj(theNod):
		try:
			return NodeToJsonObj.dictNod2Json[theNod]
		except KeyError:
			jsonObj = NodeJson(theNod)
			NodeToJsonObj.dictNod2Json[theNod] = jsonObj
			return jsonObj

	NodeToJsonObj.dictNod2Json = dict()

	links = []
	for subj, pred, obj in grph:
		# This applies only to entity.py : In rendering based on Json, scripts are not displayed as nodes,
		# but in hierarchical menus. The node must not appear at all.

		# PROBLEME: On voit toujours les nodes !!! Mais sans les aretes !!
		# C EST PARCE QUE LES NODES DES SCRIPTS CONTIENNENT LEURS PROPRES INFOS.
		# DONC, QUAND EN MODE JSON, IL FAUT VRAIMNENT NE PAS APPELER entity_dirmenu_only.py, DU TOUT !

		if pred == pc.property_script:
			sys.stderr.write("continue subj=%s obj=%s\n"%(subj,obj))
			continue

		# Normal data scripts are not accepted. This should apply only to file_directory.py and file_to_mime.py
		if not ScriptForJson(subj):
			continue

		if not ScriptForJson(obj):
			continue

		subjObj = NodeToJsonObj(subj)
		subj_id = subjObj.m_index

		propNam = PropToShortPropNam(pred)

		# TODO: BUG: If several nodes for the same properties, only the last one is kept.
		if isinstance(obj, (rdflib.URIRef, rdflib.BNode)):
			objObj = NodeToJsonObj(obj)
			obj_id = objObj.m_index
			# "value" is for the class, for example ".link10".
			links.extend([{'source': subj_id, 'target': obj_id, 'link_prop': propNam, 'value': 10}])

			# TODO: Add the name corresponding to the URL, in m_info_dict so that some elements
			# of the tooltip would be clickable. On the other hand, one just need to merge
			# the nodes relative to the object, by right-clicking.
		elif isinstance(obj, (rdflib.Literal)):
			if pred == pc.property_information:
				try:
					subjObj.m_info_list.append( str(obj.value) )
				except UnicodeEncodeError:
					# 'ascii' codec can't encode character u'\xf3' in position 17: ordinal not in range(128)
					# https://stackoverflow.com/questions/9942594/unicodeencodeerror-ascii-codec-cant-encode-character-u-xa0-in-position-20
					subjObj.m_info_list.append( obj.value.encode('utf-8') )
			else:
				if isinstance(obj.value, six.integer_types) or isinstance(obj.value, six.string_types):
					subjObj.m_info_dict[propNam] = obj.value
				else:
					# If the value cannot be serializable to JSON.
					subjObj.m_info_dict[propNam] = type(obj.value).__name__
		else:
			raise "Cannot happen here"

	# Now, this creates the nodes sent as json objects.
	numNodes = len(NodeToJsonObj.dictNod2Json)
	nodes = [None] * numNodes
	for nod in NodeToJsonObj.dictNod2Json:
		nodObj = NodeToJsonObj.dictNod2Json[nod]
		nod_titl = nodObj.m_label
		nod_id = nodObj.m_index
		obj_link = nod
		# sys.stderr.write("nod_titl=%s obj_link=%s\n"%(nod_titl,obj_link))
		# The URL must not contain any HTML entities when in a XML or SVG document,
		# and therefore must be escaped. Therefore they have to be unescaped when transmitted in JSON.
		# This is especially needed for RabbitMQ because the parameter defining its connection name
		# has the form: "Url=LOCALHOST:12345,Connection=127.0.0.1:51748 -> 127.0.0.1:5672"

		# HTTP_MIME_URL
		the_survol_nam = HTMLParser().unescape(nod_titl) # MUST UNESCAPE HTML ENTITIES !
		the_survol_url = HTMLParser().unescape(obj_link)

		nodes[nod_id] = {
			'name'             : the_survol_nam,
			"type"             : 3, # This is temporary, for coloring and will be removed.
			# Theoretically, this URL should be HTML unescaped then CGI escaped.
			# 'survol_url'       : obj_link,
			#'x'       : 500,
			#'y'       : 500,
			#'number'  : 50,
			'survol_url'       : the_survol_url,
			'fill'             : nodObj.m_color,
			'entity_class'     : nodObj.m_class, # TODO: Maybe not needed because also in the URL ?
			'survol_info_list' : nodObj.m_info_list,
			'survol_info_dict' : nodObj.m_info_dict
		}

	graph = {}
	graph["page_title"] = page_title
	graph["nodes"] = nodes
	graph["links"] = links

	WrtHeader('application/json')
	print(json.dumps(graph, indent=2))

# This returns a tree of scripts, usable as a contextual menu.
# The RDF content is already created, so this keeps only the nodes related to scripts.
# TODO: It would be faster to keep only the tree of scripts. The script "entity.py"
# should have a different output when mode=json.
# It does not return a network but a tree to be displayed in a contextual menu.
# It has a completely different layout as a normal RDF transformed into JSON,
# so probably the URL should be different as well.
# Input example: "http://127.0.0.1:8000/htbin/entity.py?xid=CIM_Process.Handle=3812&mode=json"

# TODO: Should add WBEM and WMI ?

def Grph2Menu(page_title, error_msg, isSubServer, parameters, grph):
	# For each node, the subscripts. Therefore it can only be a directory.
	NodesToItems = {}

	# Nodes of scripts which have a parent.
	NodesWithParent = set()

	# Later used to calculate the list of scripts which do not have a parent
	# directory: They will be displayed at the top of the contextual menu.
	SubjectNodes = set()

	NodeToMenuJsonObj = dict()

	# The name of each node.
	NodesToNames = dict()

	for subj, pred, obj in grph:
		if pred == pc.property_script:
			#sys.stderr.write("subj=%s\n"%str(subj))
			#sys.stderr.write("obj=%s\n"%str(obj))
			try:
				NodesToItems[subj].append(obj)
			except KeyError:
				NodesToItems[subj] = [obj]

			if isinstance(obj, (rdflib.Literal)):
				# This is the name of a subdirectory containing scripts.
				# sys.stderr.write("obj LITERAL=%s\n"%str(subj))
				NodesToNames[obj] = obj

			NodesWithParent.add(obj)
			SubjectNodes.add(subj)
		elif pred == pc.property_information:
			if isinstance(obj, (rdflib.Literal)):
				#sys.stderr.write("subj=%s\n"%str(subj))
				#sys.stderr.write("obj.value=%s\n"%obj.value)
				NodesToNames[subj] = obj.value
			else:
				raise "Cannot happen here also"
		else:
			pass

	TopLevelNodes = SubjectNodes - NodesWithParent

	#sys.stderr.write("TopLevelNodes=%s\n"%str(TopLevelNodes))

	#sys.stderr.write("\n")
	for oneRdfNod in NodesToItems:
		lstItem = NodesToItems[oneRdfNod]
		# sys.stderr.write("oneRdfNod=%s l=%d\n"%(oneRdfNod,len(lstItem)))
	#sys.stderr.write("\n")

	#sys.stderr.write("\n")
	for oneRdfNod in NodesToNames:
		nam = NodesToNames[oneRdfNod]
		# sys.stderr.write("oneRdfNod=%s nam=%s\n"%(oneRdfNod,nam))
	#sys.stderr.write("\n")

	# The output result must be sorted.
	def AddStuff(theNodList,depth=0):
		listJsonItems = {}

		for oneRdfNod in theNodList:
			#sys.stderr.write("oneRdfNod=%s\n"%oneRdfNod)
			oneJsonNod = {}
			# This should be the sort key.
			oneJsonNod["name"] = NodesToNames.get(oneRdfNod,"No name")
			# sys.stderr.write( (" " * depth) + "name=%s\n" % (oneJsonNod["name"]) )
			oneJsonNod["url"] = oneRdfNod

			# Maybe it does not have subitems.
			try:
				lstItem = NodesToItems[oneRdfNod]
				oneJsonNod["items"] = AddStuff(lstItem,depth+1)
			except KeyError:
				pass

			listJsonItems[oneRdfNod] = oneJsonNod
		return listJsonItems


	menuJson = AddStuff(TopLevelNodes)

	# sys.stderr.write("menuJson=%s\n"%str(menuJson))

	# There is only one top-level element.
	oneMenuVal = {}
	for oneMenuKey in menuJson:
		oneMenuVal = menuJson[oneMenuKey]["items"]
		break

	#sys.stderr.write("menuJson=%s\n"%str(oneMenuVal))

	WrtHeader('application/json')
	print(json.dumps(oneMenuVal, sort_keys = True, indent=2))

################################################################################

# Used by all CGI scripts when they have finished adding triples to the current RDF graph.
# This just writes a RDF document which can be used as-is by browser,
# or by another scripts which will process this RDF as input, for example when merging RDF data.
# Consider adding reformatting when the output is a browser ... if this can be detected !!
# It is probably possible with the CGI environment variable HTTP_USER_AGENT.
# Also, the display preference could be stored with the Python library cookielib.
#
# AUSSI: On pourrait, sous certaines conditions, transformer la sortie en HTML ou en SVG
# (Et/ou envoyer du Javascript avec des appels rdfquery pour affichage dans le navigateur)
# Ca pourrait dependre d'une variable CGI: mode=RDF/HTML etc...
# Ici: On peut prendre la valeur de "mode" en dissequant l'URL du Referer.
#
def Grph2Rdf(grph):
	WrtHeader('text/rdf')

	# Format support can be extended with plugins,
	# but 'xml', 'n3', 'nt', 'trix', 'rdfa' are built in.
	out_dest = lib_util.DfltOutDest()
	grph.serialize( destination = out_dest, format="xml")


# This is very primitive and maybe should be replaced by a standard function,
# but lib_util.EncodeUri() replaces "too much", and SVG urls cannot encode an ampersand...
# The problems comes from "&mode=edit" or "&mode=html" etc...
# TODO: If we can fix this, then "xid" can be replaced by "entity_type/entity_id"
def UrlToSvg(url):
	if lib_util.isPlatformWindows:
		# If one ampersand only, "error on line 28 at column 75: EntityRef: expecting ';'"
		# when displaying the SVG file.
		# Windows, Python 3.2, Graphviz 2.36
		return url.replace( "&", "&amp;amp;" )
	else:
		if sys.version_info <= (2,5):
			# Linux, Python 2.5.  Tested on Mandriva.
			# Maybe we should do the same as the others.
			return url.replace( "&", "&amp;" )
		else:
			# Tested with Python 2.7 on Fedora.
			return url.replace( "&", "&amp;amp;" )

# This returns an URL to the Javascript D3 interface, editing the current data.
def UrlToMergeD3():
	callingUrl = ModedUrl("")
	htbinPrefixScript = "/htbin"
	htbinIdx = callingUrl.find(htbinPrefixScript)
	urlWithoutHost = callingUrl[htbinIdx:]

	# While we are at it, we needs the beginning of the URL.
	urlHost = callingUrl[:htbinIdx]

	sys.stderr.write("UrlToMergeD3 urlWithoutHost=%s\n"%urlWithoutHost)

	# Maybe this URL is already a merge of B64-encoded URLs:
	# urlWithoutHost="/htbin/merge_scripts.py?url=aHR0cDovy4w...LjAuMTo42h0Yml&url=aHR0cD...AuMTo4MDA"
	htbinPrefixMergeScript = "/htbin/merge_scripts.py"
	if urlWithoutHost.startswith(htbinPrefixMergeScript):
		# If so, no need to re-encode.
		urlWithoutHostB64 = urlWithoutHost[len(htbinPrefixMergeScript):]
	else:
		urlWithoutHostB64 = "?url=" + lib_util.Base64Encode(urlWithoutHost)
	sys.stderr.write("UrlToMergeD3 urlWithoutHostB64=%s\n"%urlWithoutHostB64)

	scriptD3Url = urlHost + "/survol_d3.htm" + urlWithoutHostB64
	sys.stderr.write("UrlToMergeD3 scriptD3Url=%s\n"%scriptD3Url)
	return scriptD3Url

	# Start by removing the mode.
	# If "htbin/entity.py?xid=lkjlj" replace by "survol_d3.htm?xid=lkjlj"
	# If "htbin/.../any_script.py?xid=lkjlj" replace by "survol_d3.htm?xid=lkjlj&script=.../any_script.py"
	#
	# If we want to merge in the general case, same rule but with "htbin/mergeurls.py" a la place de "survol_d3.htm"
	# and also the mode must be added.
	#
	# Peut etre devrait-on splitter entity.py en deux modules:
	# * entity_menu.py qui genere l'arborescence des scripts, c est ce qu on envoie en json.
	# * display_entity.py qui affiche l'objet et son AddInfo(), et c est ce qui est utilise par D3.
	# Et donc on rebatit entity.py a partir de ces deux elements.
	# Avantage:
	# - les menus contextuels sont plus rapides.
	# - Afficher un objet et son environnement immediat (AddInfo) est plus rapide.
	# - On met bien a part l'exploration des scripts.
	# - On retire de RDF, dans une certaine mesure, les scripts.

# In SVG/Graphiz documents, this writes the little square which contains varios informaiton.
def WriteDotLegend( page_title, topUrl, errMsg, isSubServer, parameters, stream, grph ):

	# This allows to enter directly the URL parameters, so we can access directly an object.
	# This will allow to choose the entity type, and each parameter of the URL (Taken
	# from the ontology). It also edits the parameters of the current URL.
	# TODO: MUST FINISH THIS.
	#def UrlDirectAccess():
	#	return "direct_access.py"

	# This adds links which can display the same content in a different output format.
	def LegendAddAlternateDisplayLinks(stream):
		# So we can change parameters of this CGI script.
		urlHtml = ModedUrl("html")
		urlJson = ModedUrl("json")
		urlRdf = ModedUrl("rdf")
		urlD3 = UrlToMergeD3()

		urlHtmlReplaced = UrlToSvg( urlHtml )
		urlJsonReplaced = UrlToSvg( urlJson )
		urlRdfReplaced = UrlToSvg( urlRdf )
		urlD3Replaced = UrlToSvg( urlD3 )

		# We must pass the script and the parameters.
		#  "http://127.0.0.1:8000/survol_d3.htm?xid=CIM_Directory.Name=E%3A%2FHewlett-Packard%2FSystemDiags"

		# urlD3 = "http://127.0.0.1:8000/survol_d3.htm?xid=CIM_Directory.Name=E%3A%2FHewlett-Packard%2FSystemDiags"
		# REBATIR UN URL.
		# CA DEPEND SI C EST UN SCRIPT OU BIEN ENTITY.
		# LE TRAITEMENT DE L URL EST LE MEME SI ON VEUT ENVOYER VERS merge.py:
		# ON EXTRAIT LE SCRIPT PRINCIPAL ET ON EN FAIT UN ARGUMENT "script=".
		# MAIS IL FAUT AUSSI DETECTER QUE PEUT-ETRE LE SCRIPT COURANT EST "merge.py"
		# ET DANS CE CAS IL SUFFIT DE CHANGER LE MODE.

		stream.write(
			"<tr><td align='left' colspan='2' href='" + urlHtmlReplaced + "'>" + DotUL("As HTML") + "</td></tr>"
			"<tr><td align='left' colspan='2' href='" + urlJsonReplaced + "'>" + DotUL("As JSON") + "</td></tr>"
			"<tr><td align='left' colspan='2' href='" + urlRdfReplaced + "'>" + DotUL("As RDF") + "</td></tr>"
			"<tr><td align='left' colspan='2' href='" + urlD3Replaced + "'>" + DotUL("As D3") + "</td></tr>"
		)

	# This displays the parameters of the URL and a link allowing to edit them.
	def LegendAddParametersLinks(stream,parameters):
		if len( parameters ) > 0 :
			urlEdit = ModedUrl("edit")
			urlEditReplaced = UrlToSvg( urlEdit )
			stream.write("<tr><td colspan='2' href='" + urlEditReplaced + "' align='left'>" + DotBold(DotUL( "Edit parameters" )) + "</td></tr>" )

		arguments = cgi.FieldStorage()
		for keyParam,valParam in parameters.items():
			try:
				actualParam = arguments[keyParam].value
			except KeyError:
				actualParam = valParam
			stream.write('<tr><td>%s:</td><td>%s</td></tr>' % ( keyParam, DotIt(actualParam) ) )

	#	stream.write("""
	#  rank=sink;
	#  rankdir=LR
	#  node [shape=plaintext]
	# 	""")
	stream.write("node [shape=plaintext]")

	# The first line is a title, the rest, more explanations.
	# The first line also must be wrapped if it is too long.
	# TODO: Mettre cette logique de separation ailleurs car on en a besoin si Merge.

	(page_title_first,page_title_rest) = lib_util.SplitTextTitleRest(page_title)

	page_title_first_wrapped = StrWithBr(page_title_first,2)
	page_title_rest_wrapped = StrWithBr(page_title_rest,2)
	page_title_full =  DotBold(page_title_first_wrapped) + withBrDelim + page_title_rest_wrapped

	stream.write("""
  subgraph cluster_01 {
    key [shape=none, label=<<table border="1" cellpadding="0" cellspacing="0" cellborder="0">
      <tr><td colspan="2">""" + page_title_full + """</td></tr>
 	""")

	# BEWARE: Port numbers syntax ":8080/" is forbidden in URIs: Strange bug !
	# TODO: The "Top" url should be much more visible.
	stream.write('<tr><td align="left" colspan="2" href="' + topUrl + '">' + DotBold(DotUL("Home")) + '</td></tr>')

	#urlDirectAccess = UrlDirectAccess()
	#stream.write('<tr><td align="left" colspan="2" href="' + urlDirectAccess + '">' + DotUL("Direct access") + '</td></tr>')

	#stream.write("""
    #  <tr><td align='left' colspan="2">""" + time.strftime("%Y-%m-%d %H:%M:%S") + """</td></tr>
 	#""")
	#stream.write("""
    #  <tr><td align='left' >RDF Nodes</td><td>""" + str(len(grph)) + """</td></tr>
 	#""")

	LegendAddAlternateDisplayLinks(stream)

	LegendAddParametersLinks(stream,parameters)

	# The error message could be None or an empty string.
	if errMsg:
		fullErrMsg = DotBold("Error: ") + errMsg
		stream.write('<tr><td align="left"  balign="left" colspan="2">%s</td></tr>' % StrWithBr(fullErrMsg,2))

	if isSubServer:
		urlStop = ModedUrl("stop")
		urlStopReplaced = UrlToSvg( urlStop )
		stream.write('<tr><td colspan="2" href="' + urlStopReplaced + '">' + DotUL("Stop subserver") + '</td></tr>' )
		# TODO: Add an URL for subservers management, instead of simply "stop"
		# Maybe "mode=ctrl".This will list the feeders with their entity_id.
		# So they can be selectively stopped.

	stream.write("""
      </table>>]
  }
 	""")

